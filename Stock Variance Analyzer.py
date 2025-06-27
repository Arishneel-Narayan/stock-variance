import streamlit as st
import pandas as pd
import numpy as np
import io

# --- Helper Functions ---

def process_bcf_sales_data(uploaded_file):
    """
    Processes the uploaded BCF sales Excel file to produce clean local and export sales data.
    """
    if uploaded_file is None:
        return None, None

    try:
        # Load the uploaded file's content from the first sheet only.
        df = pd.read_excel(uploaded_file, engine='openpyxl', sheet_name=0)

        # Set the second row as the header
        df = df.iloc[1:]
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

        # Format column headers
        df.columns = [str(col).capitalize() for col in df.columns]

        if df.shape[1] < 8:
            st.error("Error: The uploaded file has fewer than 8 columns.")
            return None, None

        # Split into local and export
        local_sales = df.iloc[:, :8].copy()
        export_sales = df.iloc[:, 8:].copy()

        # Rename key columns
        local_sales = local_sales.rename(columns={local_sales.columns[0]: 'Product Code', local_sales.columns[1]: 'Product Name'})
        export_sales = export_sales.rename(columns={export_sales.columns[0]: 'Product Code', export_sales.columns[1]: 'Product Name'})

        # Clean and format 'Product Code'
        for df_clean in [local_sales, export_sales]:
            df_clean['Product Code'] = pd.to_numeric(df_clean['Product Code'], errors='coerce')
            df_clean.dropna(subset=['Product Code'], inplace=True)
            df_clean['Product Code'] = df_clean['Product Code'].astype(int)

        return local_sales, export_sales

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
        st.warning("Please ensure the file is a valid Excel file with headers in the second row.")
        return None, None


def map_stock_targets(df, target_dict):
    """
    Adds a 'Stock Target' column to a DataFrame.
    """
    if df is None:
        return None
    df['Stock Target'] = df['Product Code'].map(target_dict).fillna(0).astype(int)
    return df


def analyze_stock_balance(df, stock_column_name: str):
    """
    Calculates stock balance and splits the DataFrame into overstocked and understocked items.
    """
    try:
        if df is None:
             return None, None, None

        required_columns = [stock_column_name, 'Stock Target']
        if not all(col in df.columns for col in required_columns):
            missing_col = next((col for col in required_columns if col not in df.columns), "a required column")
            st.warning(f"Analysis failed: '{missing_col}' column not found.")
            return df, pd.DataFrame(), pd.DataFrame()

        df_analyzed = df.copy()
        df_analyzed[stock_column_name] = pd.to_numeric(df_analyzed[stock_column_name], errors='coerce').fillna(0)
        # Calculate 'Balance' instead of 'Variance'
        df_analyzed['Balance'] = df_analyzed[stock_column_name] - df_analyzed['Stock Target']

        # Overstocked: current stock > target stock (Balance > 0)
        overstocked_df = df_analyzed[df_analyzed['Balance'] > 0].copy()
        # Understocked: current stock < target stock (Balance < 0)
        understocked_df = df_analyzed[df_analyzed['Balance'] < 0].copy()

        return df_analyzed, overstocked_df, understocked_df

    except Exception as e:
        st.error(f"An error occurred during balance analysis: {e}")
        return None, None, None


# --- Streamlit App UI ---

st.set_page_config(layout="wide", page_title="BCF Stock Balance Analyzer")

st.title("📊 BCF Stock Balance Analyzer")
st.markdown("An interactive tool for process optimization engineers to analyze stock levels from BCF sales data.")

# --- Session State Initialization for storing targets ---
if 'local_targets' not in st.session_state:
    st.session_state.local_targets = {10101: 5000, 10102: 7500, 10105: 4000, 10201: 10000, 99999: 1000}

if 'export_targets' not in st.session_state:
    st.session_state.export_targets = {10101: 25000, 10102: 40000, 10305: 60000, 20201: 55000}


# --- UI Sections ---
st.header("1. Upload Sales Data")
uploaded_file = st.file_uploader("Choose your BCF.xlsx file", type="xlsx")

# --- Section for Data Entry ---
st.header("2. Add or Update Stock Targets (Forecasts)")
with st.form("target_form"):
    st.write("Use this form to add a new product forecast or update an existing one.")
    col1, col2, col3 = st.columns(3)
    with col1:
        target_type = st.selectbox("Target Type", ["Local", "Export"])
    with col2:
        product_code = st.number_input("Product Code", step=1, format="%d")
    with col3:
        stock_target = st.number_input("New Target/Forecast", step=1, format="%d")

    submitted = st.form_submit_button("Update Target")
    if submitted:
        if product_code > 0 and stock_target >= 0:
            if target_type == "Local":
                st.session_state.local_targets[product_code] = stock_target
                st.success(f"Updated local target for Product Code {product_code} to {stock_target}.")
            else:
                st.session_state.export_targets[product_code] = stock_target
                st.success(f"Updated export target for Product Code {product_code} to {stock_target}.")
        else:
            st.error("Please enter a valid Product Code and Target.")

# --- Expander for viewing current targets ---
with st.expander("View Current Stock Targets"):
    col1_exp, col2_exp = st.columns(2)
    with col1_exp:
        st.subheader("Local Sales Targets")
        st.json(st.session_state.local_targets)
    with col2_exp:
        st.subheader("Export Sales Targets")
        st.json(st.session_state.export_targets)


if uploaded_file is not None:
    st.header("3. Analysis Results")
    local_sales_df, export_sales_df = process_bcf_sales_data(uploaded_file)

    if local_sales_df is not None and export_sales_df is not None:
        # Apply stock targets from session state
        local_sales_df = map_stock_targets(local_sales_df, st.session_state.local_targets)
        export_sales_df = map_stock_targets(export_sales_df, st.session_state.export_targets)

        # Analyze balance for local sales
        _, local_overstocked, local_understocked = analyze_stock_balance(local_sales_df, 'Total')
        # Analyze balance for export sales
        _, export_overstocked, export_understocked = analyze_stock_balance(export_sales_df, 'Quantity')

        # --- Display Results ---
        col1_res, col2_res = st.columns(2)

        # Define column order with 'Balance' first
        local_cols_display = ['Balance', 'Product Code', 'Product Name', 'Total', 'Stock Target']
        export_cols_display = ['Balance', 'Product Code', 'Product Name', 'Quantity', 'Stock Target']

        with col1_res:
            st.subheader("Local Sales Analysis")
            st.markdown("#### Overstocked Local Products (Stock > Target)")
            if local_overstocked is not None and not local_overstocked.empty:
                st.dataframe(local_overstocked[local_cols_display])
            else:
                st.success("✅ No overstocked local products found.")

            st.markdown("#### Understocked Local Products (Stock < Target)")
            if local_understocked is not None and not local_understocked.empty:
                st.dataframe(local_understocked[local_cols_display])
            else:
                st.success("✅ All local product stock levels are at or above target.")

        with col2_res:
            st.subheader("Export Sales Analysis")
            st.markdown("#### Overstocked Export Products (Stock > Target)")
            if export_overstocked is not None and not export_overstocked.empty:
                st.dataframe(export_overstocked[export_cols_display])
            else:
                st.success("✅ No overstocked export products found.")

            st.markdown("#### Understocked Export Products (Stock < Target)")
            if export_understocked is not None and not export_understocked.empty:
                st.dataframe(export_understocked[export_cols_display])
            else:
                st.success("✅ All export product stock levels are at or above target.")
else:
    st.info("Awaiting BCF.xlsx file to be uploaded to view analysis results.")
