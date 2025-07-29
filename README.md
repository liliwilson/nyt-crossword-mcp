# nyt crossword mcp server

An MCP server that gives an agent access to your NYT crossword solve times and statistics. Because why not be able to check with your terminal if your precious streak is at risk?

<img width="1520" height="955" alt="image" src="https://github.com/user-attachments/assets/a602ace7-4a3f-4703-b3a3-d18e1dd9e0b5" />


## setup

This server is intended to be run locally. To do so, clone the git repo and install the dependencies:

```bash
git clone https://github.com/liliwilson/nyt-crossword-mcp.git && cd nyt-crossword-mcp

python3 -m venv .venv
source .venv/bin/activate  
pip install -r requirements.txt

```
After you're able to run it locally, you can connect the server to an LLM application of choice that supports MCP by using the following configuration information:

```json
{
  "nyt-crossword": {
    "command": "/path_to_dir/nyt-crossword-mcp/.venv/bin/python",
    "args": [
      "/path_to_dir/nyt-crossword-mcp/nyt_crossword_server.py"
    ],
    "env": {
      "NYT_COOKIE": "insert_your_cookie_here"
    },
    "working_directory": null
  }
}
```


### how to get nyt games cookie?
This might change in the future, but for now, you can get your NYT games cookie by opening up the network tab of dev tools on the NYT games website and looking for a cookie with the prefix `nyt-s=`.

## available tools

### `get_solve_stats()`
Get your overall crossword solving statistics including total puzzles solved, current streak, best streak, and average solve time.
### `get_recent_solves(days: int)`
Get solve times for recent days.
### `get_puzzle_details(date: str)`
Get details for a specific puzzle date (date must be in YYYY-MM-DD format).
