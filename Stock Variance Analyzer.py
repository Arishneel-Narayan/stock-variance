import streamlit as st
import pandas as pd
import numpy as np
import io

# --- Helper Functions from Your Original Script ---
# These functions will perform the core data processing. I've made minor
# adjustments to handle Streamlit's file uploader and to prevent printing
# to the console, instead showing info/errors in the app UI.

def process_bcf_sales_data(uploaded_file):
    """
    Processes the uploaded BCF sales Excel file to produce clean local and export sales data.
    """
    if uploaded_file is None:
        return None, None

    try:
        # Load the uploaded file's content into a pandas DataFrame.
        # The 'uploaded_file' from Streamlit is a file-like object.
        # Explicitly setting engine to 'openpyxl' makes the dependency clear.
        # Note: The 'openpyxl' library must be installed in your environment.
        # Run: pip install openpyxl
        df = pd.read_excel(uploaded_file, engine='openpyxl')

        # --- Data Processing and Transformation ---
        # Set the second row as the header
        df = df.iloc[1:]
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

        # Format column headers to 'Capitalize' case
        df.columns = [str(col).capitalize() for col in df.columns]

        # Check if there are enough columns to split
        if df.shape[1] < 8:
            st.error("Error: The uploaded Excel file has fewer than 8 columns and cannot be split into local and export data.")
            return None, None

        # Split the DataFrame into local and export sales
        local_sales = df.iloc[:, :8].copy()
        export_sales = df.iloc[:, 8:].copy()

        # Rename the key columns for both DataFrames
        local_sales = local_sales.rename(columns={local_sales.columns[0]: 'Product Code', local_sales.columns[1]: 'Product Name'})
        export_sales = export_sales.rename(columns={export_sales.columns[0]: 'Product Code', export_sales.columns[1]: 'Product Name'})

        # Clean both DataFrames by removing rows with empty 'Product Code'
        for df_clean in [local_sales, export_sales]:
            df_clean['Product Code'] = pd.to_numeric(df_clean['Product Code'], errors='coerce')
            df_clean.dropna(subset=['Product Code'], inplace=True)
            df_clean['Product Code'] = df_clean['Product Code'].astype(int)


        return local_sales, export_sales

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
        st.warning("Please ensure the uploaded file is a valid Excel file with the expected format (data headers in the second row).")
        return None, None


def map_stock_targets(df, target_dict):
    """
    Adds a 'Stock Target' column to a DataFrame by mapping product codes to a target dictionary.
    """
    if df is None:
        return None
    # Use .map() to add the target, fill non-matches with 0, and convert to integer.
    df['Stock Target'] = df['Product Code'].map(target_dict).fillna(0).astype(int)
    return df


def analyze_stock_variance(df, stock_column_name: str):
    """
    Calculates stock variance and splits the DataFrame into overstocked and understocked items.
    """
    try:
        if df is None:
             return None, None, None

        required_columns = [stock_column_name, 'Stock Target']
        if not all(col in df.columns for col in required_columns):
            missing_col = next((col for col in required_columns if col not in df.columns), "a required column")
            st.warning(f"Could not perform variance analysis because '{missing_col}' was not found.")
            return None, None, None

        df_analyzed = df.copy()
        # Sanitize the stock column to ensure it's numeric for calculation
        df_analyzed[stock_column_name] = pd.to_numeric(df_analyzed[stock_column_name], errors='coerce').fillna(0)
        df_analyzed['Variance'] = df_analyzed['Stock Target'] - df_analyzed[stock_column_name]

        # Create DataFrames for overstocked and understocked items
        overstocked_df = df_analyzed[df_analyzed['Variance'] < 0].copy()
        understocked_df = df_analyzed[df_analyzed['Variance'] > 0].copy()

        return df_analyzed, overstocked_df, understocked_df

    except Exception as e:
        st.error(f"An error occurred during variance analysis: {e}")
        return None, None, None


# --- Streamlit App UI ---

st.set_page_config(layout="wide", page_title="BCF Stock Variance Analyzer")

st.title("📈 BCF Stock Variance Analyzer")
st.markdown("An interactive tool for process optimization engineers to analyze stock levels from BCF sales data.")

# --- Step 1: File Upload ---
st.header("1. Upload Sales Data")
uploaded_file = st.file_uploader("Choose your BCF.xlsx file", type="xlsx")


if uploaded_file is not None:
    # --- Step 2: Define Stock Targets (using default values from your script) ---
    st.header("2. Define Stock Targets")
    st.info("Define the target stock level for each product code. Any product not listed here will have a target of 0.")

    # Use columns for a cleaner layout
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Local Sales Targets")
        # Hardcoded dictionary for local targets
        local_targets_dict = {
            10101: 5000, 10102: 7500, 10105: 4000, 10201: 10000, 99999: 1000
        }
        st.json(local_targets_dict)


    with col2:
        st.subheader("Export Sales Targets")
        # Hardcoded dictionary for export targets
        export_targets_dict = {
            10101: 25000, 10102: 40000, 10305: 60000, 20201: 55000
        }
        st.json(export_targets_dict)


    # --- Step 3: Process and Analyze Data ---
    st.header("3. Analysis Results")

    # Process the uploaded file
    local_sales_df, export_sales_df = process_bcf_sales_data(uploaded_file)

    if local_sales_df is not None and export_sales_df is not None:
        # Apply stock targets
        local_sales_df = map_stock_targets(local_sales_df, local_targets_dict)
        export_sales_df = map_stock_targets(export_sales_df, export_targets_dict)

        # Analyze variance for local sales (assuming stock is in 'Total' column)
        _, local_overstocked, local_understocked = analyze_stock_variance(local_sales_df, 'Total')

        # Analyze variance for export sales (assuming stock is in 'Quantity' column)
        _, export_overstocked, export_understocked = analyze_stock_variance(export_sales_df, 'Quantity')

        # --- Display Results ---
        col1_res, col2_res = st.columns(2)

        with col1_res:
            st.subheader("Local Sales Analysis")
            st.markdown("#### Overstocked Local Products")
            if not local_overstocked.empty:
                st.dataframe(local_overstocked[['Product Code', 'Product Name', 'Total', 'Stock Target', 'Variance']])
            else:
                st.success("✅ No overstocked local products found.")

            st.markdown("#### Understocked Local Products")
            if not local_understocked.empty:
                st.dataframe(local_understocked[['Product Code', 'Product Name', 'Total', 'Stock Target', 'Variance']])
            else:
                st.success("✅ All local product stock levels are at or above target.")

        with col2_res:
            st.subheader("Export Sales Analysis")
            st.markdown("#### Overstocked Export Products")
            if not export_overstocked.empty:
                st.dataframe(export_overstocked[['Product Code', 'Product Name', 'Quantity', 'Stock Target', 'Variance']])
            else:
                st.success("✅ No overstocked export products found.")

            st.markdown("#### Understocked Export Products")
            if not export_understocked.empty:
                st.dataframe(export_understocked[['Product Code', 'Product Name', 'Quantity', 'Stock Target', 'Variance']])
            else:
                st.success("✅ All export product stock levels are at or above target.")
else:
    st.info("Awaiting for BCF.xlsx file to be uploaded.")
