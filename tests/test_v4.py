import pandas as pd
from data_analysis.loader import load_csv, profile_dataframe
import json

# Create a sample dataset for testing
sample_df = pd.DataFrame({
    "Date": ["2026-01-01", "2026-01-02", "2026-01-03", "invalid_date"],
    "Product": ["Laptop", "Mouse", "Keyboard", "Laptop"],
    "Revenue": [1200, 25, 45, None]
})

sample_df.to_csv("sample.csv", index=False)

# Test the loader and profiler
df = load_csv("sample.csv")
profile = profile_dataframe(df)

print(json.dumps(profile, indent=2))