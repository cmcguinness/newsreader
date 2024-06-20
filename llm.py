import requests
import json
import os
import badjson
import utilities


#    ┌────────────────────────────────────────────────────────────────────┐
#    │                                                                    │
#    │    This is the interface to the LLMs.                              │
#    │                                                                    │
#    │    There's one sort of generic class, LLM, and three different     │
#    │    LLM specific classes.  Depending upon your environment          │
#    │    variables, one of the three classes will be used when you       │
#    │    call the LLM.  This way, I can swap around LLMs for testing     │
#    │    without changing code.                                          │
#    │                                                                    │
#    └────────────────────────────────────────────────────────────────────┘
class LLM:
    def __init__(self, model_name=None):
        if model_name is None:
            model_name = os.getenv('LLM_MODEL', 'ollama')
        model_name = model_name.lower()
        if model_name == 'huggingface':
            self.llm = HuggingFace()
            self.retry_limit = 2
        elif model_name == 'anthropic':
            self.llm = Anthropic()
            self.retry_limit = 1
        else:
            self.llm = Ollama()
            self.retry_limit = 2

    def chat(self, system_prompt, user_prompt, history):
        # It would be lovely if LLMs always worked perfectly, but they don't.
        # So we need to retry a few times if they fail.
        retries = self.retry_limit
        while retries >= 0:
            try:
                response = self.llm.chat(system_prompt, user_prompt, history, retries != self.retry_limit)
                return response
            except Exception as e:
                print(f"Error: {e}", flush=True)
                retries -= 1
                if retries < 0:
                    utilities.Utilities().stop_process()                # If we can't get a response, we need to stop the program
                print(f"Retrying LLM call", flush=True)

    #    ┌──────────────────────────────────────────────────────────┐
    #    │    Each LLM has a sweet-spot of how many articles it     │
    #    │    can tag in one call without starting to generate      │
    #    │    errors.  You will want to tune the parameter per      │
    #    │    model. If you start seeing a lot of retries or        │
    #    │    even failures, you may need to decrease the batch     │
    #    │    size.  If you never see retries, maybe increase.      │
    #    └──────────────────────────────────────────────────────────┘
    def get_batch_size(self):
        return self.llm.get_batch_size()


#    ┌────────────────────────────────────────────────────────────────────┐
#    │                                                                    │
#    │    Hugging Face / Llama 8b                                         │
#    │                                                                    │
#    │    This API is free to use once you sign-up for an API Key         │
#    │    (again, free).  It's decent for small tasks.  This is the       │
#    │    wrapper for it.                                                 │
#    │                                                                    │
#    │    You'll note the weird syntax for sending in requests with       │
#    │    things like <|start_header_id|>.  Welcome to the secret         │
#    │    lives of LLMs.                                                  │
#    │                                                                    │
#    └────────────────────────────────────────────────────────────────────┘
class HuggingFace:
    def __init__(self):
        self.API_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"
        # This is how we get our API KEY -- from the environment
        self.headers = {"Authorization": f"Bearer {os.getenv('HF_API_KEY')}"}

    @staticmethod
    def get_batch_size():
        # 5 starts generating weird errors
        return 4

    # This makes the actual call to the LLM and returns the response
    def llama_query(self, payload):
        response = requests.post(self.API_URL, headers=self.headers, json=payload)
        text = response.json()[0]['generated_text']
        response_tag = "<|start_header_id|>assistant<|end_header_id|>"

        start_answer = text.find(response_tag)
        if start_answer == -1:
            return text
        return text[start_answer + len(response_tag)+2:]

    #   The interface I'm using doesn't take the OPENAI kind of array of messages format.
    #   Instead, you have to put magic token strings in the text to delineate the different
    #   parts of the conversation.  This is a helper function to build the query.
    @staticmethod
    def build_query(system_prompt, user_prompt, history):
        query = "<|begin_of_text|>\n"
        query += f"<|start_header_id|>system<|end_header_id|>\n\n{system_prompt}\n<|eot_id|>\n\n"

        for h in history:
            if h['role'] == 'user':
                query += f"<|start_header_id|>user<|end_header_id|>\n\n{h['content']}\n<|eot_id|>\n\n"
            else:
                query += f"<|start_header_id|>assistant<|end_header_id|>\n\n{h['content']}\n<|eot_id|>\n\n"

        query += f"<|start_prompt_id|>user<|end_prompt_id|>\n\n{user_prompt}\n<|eot_id|>\n\n"
        query += "<|start_header_id|>assistant<|end_header_id|>\n\n"
        return query

    # This is the externally callable chat interface
    def chat(self, system_prompt, user_prompt, history, retry):        # You might get warnings about history not being used. Ignore them
        if system_prompt is None:
            with open('system_prompt.md', 'r') as f:
                system_prompt = f.read()
        query = self.build_query(system_prompt, user_prompt, history)

        temp = 0.1 + retry * 0.9

        raw_response = self.llama_query({"inputs": query, "parameters": {
                "max_new_tokens": 250,          # I think this is the max we can ask for
                "temperature": temp
            }})
        print('Raw Response:\n', raw_response.replace('\n', ' '), flush=True)
        parsed_response = badjson.loads(raw_response)
        if type(parsed_response).__name__ == 'dict':
            parsed_response = parsed_response[list(parsed_response.keys())[0]]

        return parsed_response


#    ┌────────────────────────────────────────────────────────────────────┐
#    │                                                                    │
#    │    Anthropic Claude Haiku                                          │
#    │                                                                    │
#    │    This is not a free API to call, but it is probably the          │
#    │    cheapest of major service providers, by a mile.  So it's not    │
#    │    a bad choice if your ollama LLM is too slow and Hugging Face    │
#    │    is tired of you.                                                │
#    │                                                                    │
#    └────────────────────────────────────────────────────────────────────┘
class Anthropic:
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')

    @staticmethod
    def get_batch_size():
        return 10           # Much more powerful than the others

    def chat(self, system_prompt, user_prompt, history, retry):
        url = 'https://api.anthropic.com/v1/messages'
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        if system_prompt is None:
            with open('system_prompt.md', 'r') as f:
                system_prompt = f.read()

        # Still not sure that this is perfect, but it works
        messages = [
            {"role": "user", "content": system_prompt},
            {"role": "assistant", "content": "I am ready to assist you with your questions."}
        ]

        for h in history:
            messages.append(h)

        messages.append({"role": "user", "content": user_prompt})

        llm_input = {
            "messages": messages,
            "model": "claude-3-haiku-20240307",
            "max_tokens": 2000,
            "temperature": 0.1 + retry * 0.9
        }

        full_response = requests.post(url, headers=headers, data=json.dumps(llm_input))
        raw_response = full_response.json()['content'][0]['text']

        print('Raw Response:\n', raw_response.replace('\n', ' '), flush=True)
        parsed_response = badjson.loads(raw_response)
        if type(parsed_response).__name__ == 'dict':
            parsed_response = parsed_response[list(parsed_response.keys())[0]]

        return parsed_response


#    ┌────────────────────────────────────────────────────────────────────┐
#    │                                                                    │
#    │    Ollama Desktop LLM                                              │
#    │                                                                    │
#    │    If you have a GPU that Ollama supports, this is a slow but      │
#    │    interesting choice.                                             │
#    │                                                                    │
#    └────────────────────────────────────────────────────────────────────┘
class Ollama:
    def __init__(self, model_name='phi3:mini'):

        self.use_json = True
        self.url = 'http://localhost:11434/api/chat'
        self.model = model_name

    @staticmethod
    def get_batch_size():
        return 1

    def chat(self, system_prompt, user_prompt, history, retry):
        if system_prompt is None:
            with open('system_prompt.md', 'r') as f:
                system_prompt = f.read()

        messages = [{'role': 'system', 'content': system_prompt}]

        for h in history:
            messages.append(h)
        messages.append({'role': 'user', 'content': user_prompt})

        llm_input = {
            'model': self.model,
            'messages': messages,
            'stream': False,
            'format': 'json',
            'num_ctx': 8192,
            'temperature': 0.1 + retry * 0.9,
        }
        headers = {
            "Content-Type": "application/json"
        }

        full_response = requests.post(self.url, headers=headers, data=json.dumps(llm_input))
        raw_response = full_response.json()['message']['content']
        parsed_response = None
        if self.use_json:
            try:
                print('Raw Response:\n', raw_response.replace('\n', ' '), flush=True)
                parsed_response = badjson.loads(raw_response)

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}", flush=True)
                print(f"User prompt was: {user_prompt}", flush=True)
                raise

        return parsed_response
