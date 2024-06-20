#    ┌────────────────────────────────────────────────────────────────────┐
#    │                                                                    │
#    │                              Bad JSON                              │
#    │                                                                    │
#    │    You tell an LLM "generate JSON". You reinforce that in the      │
#    │    prompt. So does it get it right it all the time? Oh hell no.    │
#    │                                                                    │
#    │    In fact, a shocking amount of the time it glitches on the       │
#    │    JSON.  Maybe it uses ' instead of ".  Maybe it forgets a        │
#    │    comma.  Maybe it prattles on at the end with some               │
#    │    commentary.                                                     │
#    │                                                                    │
#    │    Regardless, if you just try to naively parse JSON, it's         │
#    │    going to blow up, often.                                        │
#    │                                                                    │
#    │    This module applies a series of heuristics to try to repair     │
#    │    broken JSON and recover the data.                               │
#    │                                                                    │
#    └────────────────────────────────────────────────────────────────────┘
import json
from enum import Enum, auto


#    ┌──────────────────────────────────────────────────────────┐
#    │              Python does not do enums well.              │
#    └──────────────────────────────────────────────────────────┘
class JsonState(Enum):
    before_json = auto()
    in_json = auto()
    after_brace = auto()
    in_single_quote_string = auto()
    in_double_quote_string = auto()


#    ┌──────────────────────────────────────────────────────────┐
#    │    The model here is a sort of state machine to run      │
#    │    across the stringified version of the bad JSON and    │
#    │    catch and clean up problems as we come across         │
#    │    them.                                                 │
#    │                                                          │
#    │    With luck, when we're done, we can call               │
#    │    json.loads() and get a good result even if the        │
#    │    JSON is broken.                                       │
#    │                                                          │
#    │    If not, we let the exception bubble up to our         │
#    │    callers.                                              │
#    └──────────────────────────────────────────────────────────┘
def loads(bad_json_string: str) -> dict | list:

    good_json = ''

    state = JsonState.before_json
    last_was_escape = False

    level = 0

    # We'll loop through the stringified JSON character by character, maintaining state to indicate
    # where we are in the JSON, and what we need to do to clean it up

    for json_character in bad_json_string:

        #   This allows us to get rid of all the ```json and ``` before the start of the JSON
        #   Also, if there's any verbiage before the JSON, we'll just ignore it
        if state == JsonState.before_json:
            # Eat up anything before the start of the JSON
            if json_character != '{' and json_character != '[':
                continue
            good_json += json_character
            state = JsonState.in_json
            level = 1
            continue

        # Sometimes, I've seen JSON that looks like [{'key': 'value'} {'key': 'value'}], where there's
        # a comma missing between the two dictionaries.
        if state == JsonState.after_brace:
            # Eat up any whitespace after the brace
            if json_character == '\n':
                continue
            if json_character == ' ':
                continue

            # If we see a brace, we need to insert a comma
            if json_character == '{':
                good_json += ','

            # Regardless of whether we added a comma or not, we're no longer "after the brace" so
            # we'll resume normal JSON processing
            state = JsonState.in_json
            # Fall through to the next if

        # Here we're looking for a few common problems
        if state == JsonState.in_json:

            # Single quotes are illegal in JSON, so we need to convert them to double quotes
            if json_character == "'":
                good_json += '"'
                state = JsonState.in_single_quote_string

            # Double quotes are proper, but we need to know we're inside a string to handle newlines
            elif json_character == '"':
                state = JsonState.in_double_quote_string
                good_json += '"'

            # We don't want any extraneous characters past the end of the JSON
            # So we detect the end of the JSON by counting the number of open and close square and curly brackets
            elif json_character == '[' or json_character == '{':
                good_json += json_character
                level = level + 1
            elif json_character == ']' or json_character == '}':
                level = level - 1
                good_json += json_character
                if level == 0:
                    break  # We're done
            else:
                # Newlines outside of quotes are legal, but unnecessary
                if json_character != '\n':
                    good_json += json_character
            continue

        if state == JsonState.in_single_quote_string:
            # Single quotes are illegal in JSON, so we need to convert them to double quotes
            # Note that if you print out a python dictionary without json.dumps, it will use single quotes,
            # so this is not an uncommon problem.
            if json_character == "'" and last_was_escape == False:
                good_json += '"'
                state = JsonState.in_json
                continue

            if json_character == '\\':
                last_was_escape = True
                good_json += json_character
                continue

            last_was_escape = False
            # Newlines inside of quotes are illegal, so we need to convert them to '\\n'
            if json_character == '\n':
                good_json += '\\n'
            else:
                good_json += json_character

            continue

        if state == JsonState.in_double_quote_string:
            if json_character == '"' and last_was_escape == False:
                good_json += '"'
                state = JsonState.in_json
                continue

            if json_character == '\\':
                last_was_escape = True
                good_json += json_character
                continue

            last_was_escape = False

            # Newlines inside of quotes are illegal, so we need to convert them to '\\n'
            if json_character == '\n':
                good_json += '\\n'
            else:
                good_json += json_character
            continue

        # Should never happen, if it does, bug in the code
        print('Illegal state in bad_json_loads')


    good_json = good_json.strip()

    # Any lingering ``` at the end of the JSON? Remove it
    if good_json[-3:] == '```':
        good_json = good_json[:-3]

    # One last heuristic: sometimes the closing ] or } is missing
    if good_json[0] == '[' and good_json[-1] != ']':
        good_json += ']'

    if good_json[0] == '{' and good_json[-1] != '}':
        good_json += '}'

    # This is optimistic
    print(f"Supposedly Good JSON:\n{good_json}", flush=True)

    try:
        # Here's where the rubber meets the road
        parsed_response = json.loads(good_json)

        # Great, we got legal JSON. We may need to do some post-processing:
        # We are expecting a list of dictionaries, each one with a 'tags' key
        # But LLMs have been known to do something like { "results": [ { "tags": [ "tag1", "tag2" ] } ] }
        # Let's look at the structure of the JSON we got back and see if there's anything to fix

        # Remember, we expect a list...
        if type(parsed_response) is dict:
            # So not quite right.  Does it have a 'tags' key? If so, is it a list of strings (tags)?
            if 'tags' in parsed_response and type(parsed_response['tags']) is list and type(parsed_response['tags'][0]) is str:
                # Aha! This is a single response, so make it into an array of dictionaries for consistency
                parsed_response = [parsed_response]
            else:
                # of it's a dictionary with a single key, and that key is a list of dictionaries
                if type(parsed_response[list(parsed_response.keys())[0]]) is list and type(
                        parsed_response[list(parsed_response.keys())[0]][0]) is dict:
                    parsed_response = parsed_response[list(parsed_response.keys())[0]][0]

            # If it's not one of these two, then I have no idea, so let it fail elsewhere and we can debug it

    except json.JSONDecodeError as e:
        # Still not legal JSON, so we need to see what we got, and why it failed
        # And then we'll either fix this code, or try to fix the LLM interface
        print(f"Error parsing JSON: {e}", flush=True)
        print(f"JSON: {good_json}", flush=True)
        raise

    return parsed_response

# This is a quick test of the loads function
if __name__ == '__main__':
    test_bad_json = '''
```json
{
  "error": 'The model is currently serving too many requests. Please try again later.'
}
```
'''
    print("Bad JSON:")
    print(test_bad_json)
    parsed = loads(test_bad_json)
    print('Parsed:')
    print(json.dumps(parsed, indent=4))
