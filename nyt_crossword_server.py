from typing import Any, Dict

import httpx
import os
from datetime import datetime, timedelta
import logging
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

mcp = FastMCP("nyt-crossword")

NYT_API_BASE = "https://www.nytimes.com/svc/crosswords"
PUZZLE_INFO_ENDPOINT = "/v3/36569100/puzzles.json?publish_type=daily&date_start={start_date}&date_end={end_date}"
PUZZLE_STATS_ENDPOINT = "/v6/game/{id}.json"
USER_AGENT = "scraping personal stats"

class Config:
    def __init__(self):
        self.nyt_cookie = os.getenv("NYT_COOKIE", "")
        if not self.nyt_cookie:
            logger.error("NYT_COOKIE environment variable not set")
        else:
            logger.info("NYT cookie loaded from environment")

config = Config()

async def make_nyt_request(endpoint: str) -> Dict[str, Any] | None:
    """Make a request to the NYT Games API"""
    if not config.nyt_cookie:
        logger.error("NYT cookie not configured")
        return None
        
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Cookie": config.nyt_cookie,
        "DNT": "1"
    }
    
    url = f"{NYT_API_BASE}{endpoint}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            return None
        except Exception as e:
            logger.error(f"Request failed for {url}: {str(e)}")
            return None

async def get_puzzle_ids(start_date: str, end_date: str) -> Dict[str, int] | None:
    """Get puzzle IDs for a date range."""
    endpoint = PUZZLE_INFO_ENDPOINT.format(start_date=start_date, end_date=end_date)
    data = await make_nyt_request(endpoint)
    
    if not data or 'results' not in data:
        return None
    
    # Create a mapping of date strings to puzzle IDs
    puzzle_map = {}
    for puzzle in data['results']:
        if 'print_date' in puzzle and 'puzzle_id' in puzzle:
            puzzle_map[puzzle['print_date']] = puzzle['puzzle_id']
    
    return puzzle_map

async def get_puzzle_solve_stats(puzzle_id: int) -> Dict[str, Any] | None:
    """Get solve statistics for a specific puzzle ID."""
    endpoint = PUZZLE_STATS_ENDPOINT.format(id=puzzle_id)
    return await make_nyt_request(endpoint)

def format_solve_time(seconds: int) -> str:
    """Format solve time in seconds to readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def format_puzzle_info(puzzle_data: Dict[str, Any]) -> str:
    """Format puzzle information into a readable string."""
    if not puzzle_data:
        return "No puzzle data available"
    
    # Extract relevant information (structure may need adjustment based on actual API)
    date = puzzle_data.get('print_date', 'Unknown date')
    title = puzzle_data.get('title', 'Daily Crossword')
    editor = puzzle_data.get('editor', 'Unknown')
    solve_time = puzzle_data.get('calcs', {}).get('secondsSpentSolving', 0)
    
    result = f"""
Date: {date}
Title: {title}
Editor: {editor}
Solve Time: {format_solve_time(solve_time) if solve_time else 'Not solved'}
"""
    
    return result.strip()


@mcp.tool()
async def get_solve_stats(days: int = 30) -> str:
    """Get crossword solving statistics by analyzing recent solves.
    
    Args:
        days: Number of recent days to analyze (default: 30, max: 90)
    
    Returns summary statistics calculated from your recent solving history.
    """
    if not config.nyt_cookie:
        return "NYT cookie not configured. Set the NYT_COOKIE environment variable."
    
    if days < 1 or days > 90:
        return "Days must be between 1 and 90"
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    # Get puzzle IDs for the date range
    puzzle_ids = await get_puzzle_ids(start_date_str, end_date_str)
    if not puzzle_ids:
        return f"Unable to fetch puzzle information for the last {days} days."
    
    solved_puzzles = []
    total_puzzles = len(puzzle_ids)
    
    for date_str, puzzle_id in puzzle_ids.items():
        puzzle_stats = await get_puzzle_solve_stats(puzzle_id)
        if puzzle_stats:
            calcs = puzzle_stats.get('calcs', {})
            if calcs.get('solved'):
                solve_time = calcs.get('secondsSpentSolving', 0)
                firsts = puzzle_stats.get('firsts', {})
                cheated = bool(firsts.get('checked') or firsts.get('revealed'))
                
                solved_puzzles.append({
                    'date': date_str,
                    'solve_time': solve_time,
                    'cheated': cheated
                })
    
    if not solved_puzzles:
        return f"No solved puzzles found in the last {days} days."
    
    # Calculate statistics
    total_solved = len(solved_puzzles)
    solve_times = [p['solve_time'] for p in solved_puzzles if p['solve_time'] > 0]
    avg_time = sum(solve_times) // len(solve_times) if solve_times else 0
    fastest_time = min(solve_times) if solve_times else 0
    slowest_time = max(solve_times) if solve_times else 0
    cheated_count = sum(1 for p in solved_puzzles if p['cheated'])
    
    result = f"""
Your NYT Crossword Statistics (Last {days} days):

Puzzles Available: {total_puzzles}
Puzzles Solved: {total_solved}
Solve Rate: {(total_solved/total_puzzles*100):.1f}%
Average Solve Time: {format_solve_time(avg_time) if avg_time else 'N/A'}
Fastest Solve: {format_solve_time(fastest_time) if fastest_time else 'N/A'}
Slowest Solve: {format_solve_time(slowest_time) if slowest_time else 'N/A'}
Used Hints: {cheated_count} puzzles
"""
    
    return result.strip()

@mcp.tool()
async def get_recent_solves(days: int = 7) -> str:
    """Get recent crossword solve times.
    
    Args:
        days: Number of recent days to retrieve (default: 7)
    """
    if not config.nyt_cookie:
        return "NYT cookie not configured. Set the NYT_COOKIE environment variable."
    
    if days < 1 or days > 30:
        return "Days must be between 1 and 30"
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    # Get puzzle IDs for the date range
    puzzle_ids = await get_puzzle_ids(start_date_str, end_date_str)
    if not puzzle_ids:
        return f"Unable to fetch puzzle information for the last {days} days."
    
    solves = []
    for date_str, puzzle_id in puzzle_ids.items():
        puzzle_stats = await get_puzzle_solve_stats(puzzle_id)
        if puzzle_stats:
            # Check if puzzle was solved
            calcs = puzzle_stats.get('calcs', {})
            if calcs.get('solved'):
                solve_time = calcs.get('secondsSpentSolving', 0)
                firsts = puzzle_stats.get('firsts', {})
                cheated = bool(firsts.get('checked') or firsts.get('revealed'))
                
                solves.append({
                    'date': date_str,
                    'solve_time': solve_time,
                    'cheated': cheated
                })
    
    if not solves:
        return f"No solved puzzles found for the last {days} days."
    
    # Sort by date (most recent first)
    solves.sort(key=lambda x: x['date'], reverse=True)
    
    result = f"Recent Solves (Last {days} days):\n\n"
    
    for solve in solves:
        cheat_indicator = " (used hints)" if solve['cheated'] else ""
        result += f"Date: {solve['date']}\n"
        result += f"Solve Time: {format_solve_time(solve['solve_time'])}{cheat_indicator}\n---\n"
    
    return result.strip()

@mcp.tool()
async def get_puzzle_details(date: str) -> str:
    """Get details for a specific puzzle date.
    
    Args:
        date: Date in YYYY-MM-DD format (e.g., "2024-01-15")
    """
    if not config.nyt_cookie:
        return "NYT cookie not configured. Set the NYT_COOKIE environment variable."
    
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD (e.g., '2024-01-15')"
    
    # Get puzzle ID for the specific date
    puzzle_ids = await get_puzzle_ids(date, date)
    if not puzzle_ids or date not in puzzle_ids:
        return f"No puzzle found for {date}"
    
    puzzle_id = puzzle_ids[date]
    puzzle_stats = await get_puzzle_solve_stats(puzzle_id)
    
    if not puzzle_stats:
        return f"Unable to fetch puzzle stats for {date}"
    
    # Extract puzzle information
    calcs = puzzle_stats.get('calcs', {})
    firsts = puzzle_stats.get('firsts', {})
    
    solved = calcs.get('solved', False)
    solve_time = calcs.get('secondsSpentSolving', 0) if solved else 0
    cheated = bool(firsts.get('checked') or firsts.get('revealed')) if solved else False
    
    result = f"Puzzle Details for {date}:\n\n"
    result += f"Puzzle ID: {puzzle_id}\n"
    result += f"Status: {'Solved' if solved else 'Not solved'}\n"
    
    if solved:
        cheat_indicator = " (used hints)" if cheated else ""
        result += f"Solve Time: {format_solve_time(solve_time)}{cheat_indicator}\n"
        
        if firsts.get('opened'):
            opened_time = firsts['opened']
            result += f"First Opened: {datetime.fromtimestamp(opened_time).strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if firsts.get('solved'):
            solved_time = firsts['solved']
            result += f"Completed: {datetime.fromtimestamp(solved_time).strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return result.strip()


if __name__ == "__main__":
    # Run the server with stdio transport
    mcp.run(transport='stdio')
