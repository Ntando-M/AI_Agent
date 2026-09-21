import json

from data_analysis.loader import load_csv, load_excel
from data_analysis.profiler import profile_dataframe


# Test CSV loading
csv_path = "data/sample.csv"

df = load_csv(csv_path)

print("CSV loaded successfully")
print("Rows:", len(df))
print("Columns:", list(df.columns))


# Test profiling
profile = profile_dataframe(df)

print("\nDataFrame profile:")
print(json.dumps(profile, indent=2, default=str))


# Test Excel loading
excel_path = "data/sample_sales.xlsx"

excel_df = load_excel(excel_path)

print("\nExcel loaded successfully")
print("Rows:", len(excel_df))
print("Columns:", list(excel_df.columns))


# Test Excel profiling
excel_profile = profile_dataframe(excel_df)

print("\nExcel profile:")
print(json.dumps(excel_profile, indent=2, default=str))


print("\nV4 loader and profiler tests completed successfully.")