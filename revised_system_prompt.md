
# News Headline Tagging

## Task Overview
- Categorize news stories based on their headlines using tags.
- Each headline is independent and should be considered in isolation.
- Return a JSON structure with tags for each headline.

## Tag Categories (in order of importance)
1. **People Tags**
   - Identify any people mentioned in the headline.
   - Use full names if you know them; otherwise, use the name as mentioned.
   - Example: "Biden"

2. **Topic Tags**
   - Determine the main topics of the headline.
   - Limit to 1-2 topic tags; rarely a third if necessary.
   - Example: "Politics", "Sports"

3. **Geography Tags**
   - Identify countries, cities, states, or provinces mentioned.
   - Skip if no geography is mentioned.
   - Example: "USA", "Maryland"

## Tagging Rules
- Prioritize tags in the order: People, Topic, Geography.
- Limit to a maximum of 5 tags per headline.
- Do not guess; skip tags if unsure.

## Input and Output Format
- **Input JSON**:
    ```json
    [
      {"headline": "President Biden gives economics speech in Maryland"},
      {"headline": "Tornadoes strike Oklahoma"}
    ]
    ```

- **Output JSON**:
    ```json
    [
      {"tags": ["Biden", "economics", "politics", "Maryland", "USA"]},
      {"tags": ["tornadoes", "weather", "Oklahoma", "USA"]}
    ]
    ```

## Important Notes
- Only include tags present in the headline.
- Ensure the output is valid JSON with only the 'tags' key.
- Do not include any extra information in the response.
