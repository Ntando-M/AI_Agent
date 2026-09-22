import pandas as pd
from langchain_core.tools import tool

# Import the base analyzer functions and Pydantic models
from data_analysis.analyzer import group_by_column, filter_dataset, calculate_statistics
from models.tool_models import GroupByColumnInput, FilterDatasetInput, CalculateStatisticsInput

# The active dataframe the agent will operate on
active_df = pd.DataFrame() 

def set_active_dataframe(df: pd.DataFrame):
    """Update the global dataframe that the tools will use."""
    global active_df
    active_df = df

# ==========================================
# LANGCHAIN TOOLS
# ==========================================

@tool(args_schema=GroupByColumnInput)
def tool_group_by_column(group_column: str, aggregation_column: str, operation: str = "sum") -> str:
    """Group a dataset by one column and aggregate another numeric column."""
    try:
        result_df = group_by_column(active_df, group_column, aggregation_column, operation)
        return result_df.to_string(index=False)
    except Exception as e:
        return f"Error: {str(e)}"

@tool(args_schema=FilterDatasetInput)
def tool_filter_dataset(column: str, value: str) -> str:
    """Filter a DataFrame using an exact column-value match."""
    try:
        result_df = filter_dataset(active_df, column, value)
        return f"Filter applied successfully. {len(result_df)} rows remaining."
    except Exception as e:
        return f"Error: {str(e)}"

@tool(args_schema=CalculateStatisticsInput)
def tool_calculate_statistics(column: str) -> str:
    """Calculate deterministic descriptive statistics for a numeric column."""
    try:
        stats = calculate_statistics(active_df, column)
        return "\n".join(f"{k}: {v}" for k, v in stats.items())
    except Exception as e:
        return f"Error: {str(e)}"

# ==========================================
# AGENT INITIALIZATION
# ==========================================

def get_data_agent_tools():
    """Return the list of tools available to the agent."""
    return [
        tool_group_by_column,
        tool_filter_dataset,
        tool_calculate_statistics
    ]