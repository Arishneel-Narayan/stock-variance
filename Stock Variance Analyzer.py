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

        df_analyzed = df.copy()
        # Ensure required columns exist
        required_columns = [stock_column_name, 'Stock Target']
        if not all(col in df.columns for col in required_columns):
            missing_col = next((col for col in required_columns if col not in df.columns), "a required column")
            # This is a non-critical warning for the UI
            return df, pd.DataFrame(), pd.DataFrame()

        # Sanitize the stock column to ensure it's numeric for calculation
        df_analyzed[stock_column_name] = pd.to_numeric(df_analyzed[stock_column_name], errors='coerce').fillna(0)
        # Balance = Current Stock - Target Stock
        df_analyzed['Balance'] = df_analyzed[stock_column_name] - df_analyzed['Stock Target']

        # Overstocked: current stock > target stock (Balance > 0)
        overstocked_df = df_analyzed[df_analyzed['Balance'] > 0].copy()
        # Understocked: current stock < target stock (Balance < 0)
        understocked_df = df_analyzed[df_analyzed['Balance'] < 0].copy()

        return df_analyzed, overstocked_df, understocked_df

    except Exception as e:
        st.error(f"An error occurred during detailed balance analysis: {e}")
        return None, None, None

def create_production_priority_list(local_df, export_df):
    """
    Merges local and export data to create a single, prioritized production list.
    """
    if local_df is None or export_df is None:
        return pd.DataFrame()

    try:
        # Select and rename columns for clarity before merging
        local_subset = local_df[['Product Code', 'Product Name', 'Total', 'Stock Target']].rename(
            columns={'Total': 'Local Stock', 'Stock Target': 'Local Target'}
        )
        export_subset = export_df[['Product Code', 'Product Name', 'Quantity', 'Stock Target']].rename(
            columns={'Quantity': 'Export Stock', 'Stock Target': 'Export Target'}
        )

        # Use an outer merge to include products that might only exist in one list
        merged_df = pd.merge(
            local_subset,
            export_subset,
            on=['Product Code', 'Product Name'],
            how='outer'
        )

        # Fill NaN values with 0 and convert types
        merged_df = merged_df.fillna(0)
        for col in ['Local Stock', 'Local Target', 'Export Stock', 'Export Target']:
            merged_df[col] = merged_df[col].astype(int)

        # Calculate consolidated metrics
        merged_df['Total Current Stock'] = merged_df['Local Stock'] + merged_df['Export Stock']
        merged_df['Total Production Required'] = merged_df['Local Target'] + merged_df['Export Target']
        merged_df['Production Shortfall'] = merged_df['Total Production Required'] - merged_df['Total Current Stock']

        # Filter out products where no production is needed
        production_list = merged_df[merged_df['Production Shortfall'] > 0].copy()
        production_list.sort_values(by='Production Shortfall', ascending=False, inplace=True)

        final_columns = [
            'Production Shortfall', 'Product Code', 'Product Name',
            'Total Production Required', 'Total Current Stock',
            'Local Target', 'Export Target'
        ]
        return production_list[final_columns]

    except Exception as e:
        st.error(f"An error occurred during the final analysis: {e}")
        return pd.DataFrame()


# --- Streamlit App UI ---

st.set_page_config(layout="wide", page_title="BCF Production Priority Analyzer")

st.title("🏭 BCF Production Priority Analyzer")
st.markdown("A consolidated tool to identify and prioritize production based on total market demand versus total stock.")

# --- Session State Initialization ---
if 'local_targets' not in st.session_state:
    st.session_state.local_targets = {
    '20400407': 1000,
    '20400408': 800,
    '20400409': 500,
    '20400410': 500,
    '20400406': 500,
    '20100050': 35000,
    '20100000': 0,
    '20100170': 13000,
    '20100250': 7000,
    '20100120': 0,
    '20480100': 500,
    '20140000': 4500,
    '20140011': 1000,
    '20120000': 3000,
    '16000110': 0,
    '20700990': 600,
    '20406000': 0,
    '20500215': 1500,
    '20500200': 2000,
    '20450210': 1000,
    '20450150': 1000,
    '20450100': 2000,
    '20400300': 1000,
    '20960237': 1000,
    '20400350': 1000,
    '20400400': 1000,
    '20750140': 1000,
    '20400100': 1000,
    '20401010': 1500,
    '20200150': 4000,
    '20150000': 3000,
    '20200200': 2000,
    '20750110': 2000,
    '20750130': 1000,
    '20750149': 1000,
    '16000105': 10000,
    '16000115': 200
}
if 'export_targets' not in st.session_state:
    st.session_state.export_targets = {
    '20400407': 2000,
    '20400408': 1000,
    '20400409': 1000,
    '20400410': 1000,
    '20400406': 1000,
    '20100050': 10000,
    '20100000': 4000,
    '20100170': 13000,
    '20100250': 10000,
    '20100120': 3000,
    '20480100': 200,
    '20140000': 4000,
    '20140011': 500,
    '20120000': 3000,
    '16000110': 6000,
    '20700990': 300,
    '20406000': 3000,
    '20500215': 2000,
    '20500200': 2000,
    '20450210': 1000,
    '20450150': 500,
    '20450100': 5000,
    '20400300': 3000,
    '20960237': 500,
    '20400350': 1500,
    '20400400': 1500,
    '20750140': 2000,
    '20400100': 1200,
    '20401010': 500,
    '20200150': 3000,
    '20150000': 2000,
    '20200200': 6000,
    '20750110': 3000,
    '20750130': 1500,
    '20750149': 1000,
    '16000105': 0,
    '16000115': 0
}
# --- UI Sections ---
st.header("1. Upload Sales Data")
uploaded_file = st.file_uploader("Choose your BCF.xlsx file", type="xlsx")

st.header("2. Add or Update Stock Targets (Forecasts)")
with st.form("target_form"):
    st.write("Use this form to add a new product forecast or update an existing one.")
    col1, col2, col3 = st.columns(3)
    with col1:
        target_type = st.selectbox("Target Type", ["Local", "Export"])
    with col2:
        product_code = st.number_input("Product Code", step=1, format="%d", min_value=0)
    with col3:
        stock_target = st.number_input("New Target/Forecast", step=1, format="%d", min_value=0)

    if st.form_submit_button("Update Target"):
        if product_code > 0:
            if target_type == "Local":
                st.session_state.local_targets[product_code] = stock_target
                st.success(f"Updated local target for Product Code {product_code} to {stock_target}.")
            else:
                st.session_state.export_targets[product_code] = stock_target
                st.success(f"Updated export target for Product Code {product_code} to {stock_target}.")
        else:
            st.error("Please enter a valid Product Code.")

with st.expander("View Current Stock Targets"):
    c1, c2 = st.columns(2)
    c1.subheader("Local Sales Targets")
    c1.json(st.session_state.local_targets)
    c2.subheader("Export Sales Targets")
    c2.json(st.session_state.export_targets)


if uploaded_file is not None:
    local_sales_df, export_sales_df = process_bcf_sales_data(uploaded_file)

    if local_sales_df is not None and export_sales_df is not None:
        # Apply stock targets from session state
        local_sales_df = map_stock_targets(local_sales_df, st.session_state.local_targets)
        export_sales_df = map_stock_targets(export_sales_df, st.session_state.export_targets)

        # --- 3. Display Production Priority List ---
        st.header("3. Consolidated Production Priority List")
        st.markdown("This table shows the total units needed for each product, sorted by the most urgent requirement first.")
        production_priority_df = create_production_priority_list(local_sales_df, export_sales_df)
        if not production_priority_df.empty:
            st.dataframe(production_priority_df)
        else:
            st.success("✅ No production shortfall found. All stock levels meet or exceed the total required targets.")

        # --- 4. Display Detailed Market Analysis ---
        st.header("4. Detailed Market Analysis")
        col1_res, col2_res = st.columns(2)

        # Analyze and display local market details
        with col1_res:
            st.subheader("Local Sales Breakdown")
            _, local_overstocked, local_understocked = analyze_stock_balance(local_sales_df, 'Total')
            
            st.markdown("###### Overstocked Local Products (Stock > Target)")
            if not local_overstocked.empty:
                st.dataframe(local_overstocked[['Product Code', 'Product Name', 'Total', 'Stock Target', 'Balance']])
            else:
                st.info("No overstocked local products.")

            st.markdown("###### Understocked Local Products (Stock < Target)")
            if not local_understocked.empty:
                st.dataframe(local_understocked[['Product Code', 'Product Name', 'Total', 'Stock Target', 'Balance']])
            else:
                st.info("No understocked local products.")

        # Analyze and display export market details
        with col2_res:
            st.subheader("Export Sales Breakdown")
            _, export_overstocked, export_understocked = analyze_stock_balance(export_sales_df, 'Quantity')
            
            st.markdown("###### Overstocked Export Products (Stock > Target)")
            if not export_overstocked.empty:
                st.dataframe(export_overstocked[['Product Code', 'Product Name', 'Quantity', 'Stock Target', 'Balance']])
            else:
                st.info("No overstocked export products.")

            st.markdown("###### Understocked Export Products (Stock < Target)")
            if not export_understocked.empty:
                st.dataframe(export_understocked[['Product Code', 'Product Name', 'Quantity', 'Stock Target', 'Balance']])
            else:
                st.info("No understocked export products.")

else:
    st.info("Awaiting BCF.xlsx file to be uploaded to view the analysis.")
