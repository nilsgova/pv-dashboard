import os
import boto3
import pandas as pd
import streamlit as st
import plotly.express as px

# ✅ AWS S3 Configuration
AWS_BUCKET_NAME = "pv-monthly-reports"
AWS_REGION = "eu-central-1"

# ✅ Initialize S3 Client
s3 = boto3.client("s3", region_name=AWS_REGION)

# ✅ Function to List Available Files in S3
def list_s3_files(prefix=""):
    try:
        response = s3.list_objects_v2(Bucket=AWS_BUCKET_NAME, Prefix=prefix)
        if "Contents" in response:
            return [obj["Key"] for obj in response["Contents"] if obj["Key"].endswith(".csv")]
    except Exception as e:
        st.error(f"❌ Error fetching files from S3: {e}")
    return []

# ✅ Function to Read a CSV File from S3
def read_s3_csv(file_key):
    try:
        obj = s3.get_object(Bucket=AWS_BUCKET_NAME, Key=file_key)
        return pd.read_csv(obj["Body"])
    except Exception as e:
        st.error(f"❌ Error reading {file_key} from S3: {e}")
        return None

# ✅ Load CSV Files from S3 (Instead of Local Files)
accessibility_files = list_s3_files("accessibility_report_")
seo_files = list_s3_files("seo_report_")
broken_links_files = list_s3_files("broken_links_report_")

# ✅ Extract Unique Month Names (YYYY-MM) from Filenames
def extract_unique_months(files):
    return sorted(set([f.split("_")[2][:7] for f in files if "_" in f]))

accessibility_months = extract_unique_months(accessibility_files)
seo_months = extract_unique_months(seo_files)
broken_links_months = extract_unique_months(broken_links_files)

# ✅ Set Up Streamlit Dashboard
st.set_page_config(page_title="P&V Analysis Dashboard", layout="wide")
st.title("P&V Analysis Dashboard (AWS S3)")

# ✅ Create Main Tabs
main_tabs = st.tabs(["Accessibility", "Broken Links", "SEO"])

### Accessibility Tab ###
with main_tabs[0]:
    st.header("Accessibility Dashboard")

    if not accessibility_files:
        st.warning("No Accessibility reports found.")
    else:
        # ✅ Create Monthly Sub-Tabs
        tabs = st.tabs(accessibility_months)

        for i, month in enumerate(accessibility_months):
            with tabs[i]:
                st.subheader(f"Accessibility Data for {month}")

                # ✅ Filter files for the selected month
                month_files = [f for f in accessibility_files if f.split("_")[2].startswith(month)]
                combined_data = pd.concat([read_s3_csv(f) for f in month_files])

                # Visualization: Impact Distribution (Bar Chart)
                st.subheader("Impact Distribution")
                desired_order = ["critical", "serious", "moderate", "minor"]
                impact_counts = combined_data["Impact"].value_counts().reindex(desired_order, fill_value=0)

                # Convert to DataFrame for Plotly
                impact_counts_df = impact_counts.reset_index()
                impact_counts_df.columns = ["Impact", "Count"]

                # Create a custom color map for the impact levels
                color_map = {"critical": "red", "serious": "orange", "moderate": "yellow", "minor": "green"}

                # Plot the bar chart using Plotly
                fig = px.bar(
                    impact_counts_df,
                    x="Impact",
                    y="Count",
                    color="Impact",
                    color_discrete_map=color_map,
                    title="Impact Distribution",
                    labels={"Count": "Number of Violations", "Impact": "Severity"},
                )
                st.plotly_chart(fig, use_container_width=True)

                # Create four tabs: Critical, Serious, Moderate, Minor
                impact_tabs = st.tabs(["Critical", "Serious", "Moderate", "Minor"])

                for j, impact_level in enumerate(desired_order):
                    with impact_tabs[j]:
                        st.subheader(f"{impact_level.capitalize()} Violations")

                        # Filter data for this impact level
                        impact_data = combined_data[combined_data["Impact"] == impact_level]

                        if impact_data.empty:
                            st.success(f"✅ No {impact_level} violations found!")
                        else:
                            # Group by Violation ID and count occurrences
                            violation_counts = impact_data["Violation ID"].value_counts().reset_index()
                            violation_counts.columns = ["Violation ID", "Count"]

                            # Dropdown to select a specific violation ID
                            selected_violation = st.selectbox(
                                "Select a Violation ID:",
                                violation_counts["Violation ID"],
                                format_func=lambda x: f"{x} ({violation_counts[violation_counts['Violation ID'] == x]['Count'].values[0]} occurrences)"
                            )

                            # Get the description and recommendation for the selected violation
                            violation_details = impact_data[impact_data["Violation ID"] == selected_violation].iloc[0]
                            st.markdown(f"""
                                **Violation Description:** {violation_details["Description"]}
                                
                                **Recommendation:** {violation_details["Recommendation"]}
                            """)

                            # Display list of URLs with this violation
                            st.markdown("#### Affected URLs")
                            violation_urls = impact_data[impact_data["Violation ID"] == selected_violation][["URL", "Element", "Location"]]
                            st.dataframe(violation_urls)

                
        # Display the raw data
        st.write("Raw Data")
        st.dataframe(combined_data)

### Broken Links Tab ###
with main_tabs[1]:
    st.header("Broken Links Dashboard")

    if not broken_links_files:
        st.warning("No Broken Links reports found.")
    else:
        # ✅ Create Monthly Sub-Tabs
        tabs = st.tabs(broken_links_months)

        for i, month in enumerate(broken_links_months):
            with tabs[i]:
                st.subheader(f"Broken Links Data for {month}")

                # ✅ Filter files for the selected month
                month_files = [f for f in broken_links_files if f.split("_")[2].startswith(month)]
                combined_data = pd.concat([read_s3_csv(f) for f in month_files])
                # Load data for the selected month, but ignore empty or corrupt files
                valid_files = []
                for f in month_files:
                    try:
                        df = pd.read_csv(f)
                        if not df.empty:  # Ensure file is not empty
                            valid_files.append(df)
                        else:
                            st.warning(f"Skipping empty file: {f}")
                    except pd.errors.EmptyDataError:
                        st.warning(f"Skipping empty file: {f}")
                    except Exception as e:
                        st.error(f"Error reading file {f}: {e}")

                # Combine only valid, non-empty files
                if valid_files:
                    combined_data = pd.concat(valid_files)
                    
                    # Display the raw data
                    st.write("Raw Data")
                    st.dataframe(combined_data)

                    # Proceed with visualization...
                else:
                    st.warning("No valid Broken Links data available for this month.")


                # Display the raw data
                st.write("Raw Data")
                st.dataframe(combined_data)

                # Add specific visualizations or analyses for broken links here
                st.write("Add Broken Links visualizations here!")

### SEO Tab ###
with main_tabs[2]:
    st.header("SEO Dashboard")

    if not seo_files:
        st.warning("No SEO reports found.")
    else:
        # ✅ Create Monthly Sub-Tabs
        tabs = st.tabs(seo_months)

        for i, month in enumerate(seo_months):
            with tabs[i]:
                st.subheader(f"SEO Data for {month}")

                # ✅ Filter files for the selected month
                month_files = [f for f in seo_files if f.split("_")[2].startswith(month)]

                # ✅ Read files from S3 & filter out empty ones
                valid_files = []
                for file in month_files:
                    df = read_s3_csv(file)
                    if df is not None and not df.empty:
                        valid_files.append(df)

                # ✅ Combine only valid, non-empty files
                if valid_files:
                    combined_data = pd.concat(valid_files)

                    # ✅ Ensure `SEO Score`, `Title Length`, `Description Length` are numeric
                    numeric_cols = ["SEO Score", "Title Length", "Description Length"]
                    for col in numeric_cols:
                        combined_data[col] = pd.to_numeric(combined_data[col], errors="coerce")

                    # ✅ Remove invalid rows (rows with NaN in SEO Score, Title Length, or Description Length)
                    combined_data = combined_data.dropna(subset=numeric_cols)

                    # ✅ SEO Score Categorization
                    bins = [0, 49, 69, 79, 89, 100]
                    labels = ["Very Bad (0-49)", "Bad (50-69)", "Average (70-79)", "Good (80-89)", "Very Good (90-100)"]
                    combined_data["SEO Category"] = pd.cut(combined_data["SEO Score"], bins=bins, labels=labels, include_lowest=True)

                    # ✅ SEO Score Analysis (Collapsible Dropdown)
                    with st.expander("📌 SEO Score Analysis",expanded=True):
                        st.subheader("SEO Score Analysis")
                        # ✅ SEO Score Distribution
                        seo_category_counts = combined_data["SEO Category"].value_counts().reindex(labels, fill_value=0)

                        fig_seo = px.bar(
                            seo_category_counts.reset_index(),
                            y="SEO Category",
                            x=seo_category_counts.values,
                            title="SEO Score Distribution",
                            labels={"x": "Number of Pages", "SEO Category": "SEO Score Category"},
                            orientation="h",  # Horizontal bar chart
                            color="SEO Category",
                            color_discrete_map={
                                "Very Bad (0-49)": "red",
                                "Bad (50-69)": "orange",
                                "Average (70-79)": "yellow",
                                "Good (80-89)": "blue",
                                "Very Good (90-100)": "green"
                            }
                        )
                        st.plotly_chart(fig_seo, use_container_width=True)

                        # 📂 SEO Score Tabs
                        score_tabs = st.tabs(labels)

                        for i, category in enumerate(labels):
                            with score_tabs[i]:
                                category_data = combined_data[combined_data["SEO Category"] == category]

                                if category_data.empty:
                                    st.warning(f"No pages in the {category} category.")
                                else:
                                    st.subheader(f"Pages in {category} Category")
                                    st.write(f"Total pages: **{len(category_data)}**")

                                    # Sort pages by SEO score
                                    category_data_sorted = category_data.sort_values(by="SEO Score", ascending=True)

                                    # Display data
                                    st.dataframe(category_data_sorted[["URL", "SEO Score"]])

                    # ✅ Meta Data Analysis (Collapsible Dropdown)
                    with st.expander("📌 Meta Data Analysis",expanded=True):
                        st.subheader("Meta Data Analysis")

                        # ✅ Fix Meta Title & Description Counting
                        st.markdown("**Meta Title & Description Coverage**")
                        meta_title_counts = combined_data["Meta Title"].apply(lambda x: "Missing" if x == "Missing" else "Present").value_counts()
                        meta_desc_counts = combined_data["Meta Description"].apply(lambda x: "Missing" if x == "Missing" else "Present").value_counts()

                        # ✅ Ensure Pie Charts Always Show Missing vs Present
                        meta_title_counts = meta_title_counts.reindex(["Present", "Missing"], fill_value=0)
                        meta_desc_counts = meta_desc_counts.reindex(["Present", "Missing"], fill_value=0)

                        # Define Meta Description Pie Chart
                        fig_meta_desc = px.pie(
                            names=meta_desc_counts.index, values=meta_desc_counts.values,
                            title="Meta Description Presence",
                            color_discrete_sequence=["purple", "orange"]
                        )

                        # Define Meta Title Pie Chart
                        fig_meta_title = px.pie(
                            names=meta_title_counts.index, values=meta_title_counts.values,
                            title="Meta Title Presence",
                            color_discrete_sequence=["blue", "red"]
                        )

                        # Create two columns for side-by-side charts
                        col1, col2 = st.columns(2)

                        # Meta Title Pie Chart (Left Column)
                        with col1:
                            st.plotly_chart(fig_meta_title, use_container_width=True)

                        # Meta Description Pie Chart (Right Column)
                        with col2:
                            st.plotly_chart(fig_meta_desc, use_container_width=True)

                        # Define length thresholds (Include Missing Titles & Descriptions as "Too Short")
                        title_too_short = combined_data[
                            (combined_data["Title Length"] < 30) | (combined_data["Title Length"] == 0)
                        ]
                        title_too_long = combined_data[combined_data["Title Length"] > 60]

                        description_too_short = combined_data[
                            (combined_data["Description Length"] < 50) | (combined_data["Description Length"] == 0)
                        ]
                        description_too_long = combined_data[combined_data["Description Length"] > 160]

                        # Create two columns for side-by-side lists
                        col1, col2 = st.columns(2)

                        # 📜 List of pages with **Title Issues**
                        with col1:
                            st.subheader("Pages with Title Length Issues")
                            st.markdown("""
                            <div style="padding: 8px; background-color: rgb(255 255 255 / 8%); border-radius: 5px; font-size: 14px;">
                            <b>SEO Best Practices:</b> Titles should be between <b>50-60 characters</b> for optimal visibility. 
                            Short titles may lack enough context, while long titles can get <b>cut off</b> in search results.
                            </div>
                            """, unsafe_allow_html=True)

                            # Count and display the number of issues
                            short_title_count = len(title_too_short)
                            long_title_count = len(title_too_long)

                            st.markdown(f"#### **Too Short Titles ({short_title_count})**")
                            if title_too_short.empty:
                                st.success("✅ No titles are too short!")
                            else:
                                st.dataframe(title_too_short[["URL", "Meta Title", "Title Length"]])

                            st.markdown(f"#### **Too Long Titles ({long_title_count})**")
                            if title_too_long.empty:
                                st.success("✅ No titles are too long!")
                            else:
                                st.dataframe(title_too_long[["URL", "Meta Title", "Title Length"]])

                        # 📜 List of pages with **Description Issues**
                        with col2:
                            st.subheader("Pages with Description Length Issues")
                            st.markdown("""
                            <div style="padding: 8px; background-color: rgb(255 255 255 / 8%); border-radius: 5px; font-size: 14px;">
                            <b>SEO Best Practices:</b> Meta descriptions should be between <b>50-160 characters</b>. 
                            A well-written description can **increase click-through rates**, while too long descriptions may be <b>truncated</b>.
                            </div>
                            """, unsafe_allow_html=True)

                            # Count and display the number of issues
                            short_desc_count = len(description_too_short)
                            long_desc_count = len(description_too_long)

                            st.markdown(f"#### **Too Short Descriptions ({short_desc_count})**")
                            if description_too_short.empty:
                                st.success("✅ No descriptions are too short!")
                            else:
                                st.dataframe(description_too_short[["URL", "Meta Description", "Description Length"]])

                            st.markdown(f"#### **Too Long Descriptions ({long_desc_count})**")
                            if description_too_long.empty:
                                st.success("✅ No descriptions are too long!")
                            else:
                                st.dataframe(description_too_long[["URL", "Meta Description", "Description Length"]])
                                
                    # ✅ H1 Tag Presence
                    with st.expander("📌 H1 Tag Issues Overview",expanded=True):
                        st.subheader("H1 Tag Issues Overview")
                        st.markdown("""
                        <div style="padding: 8px; background-color: rgb(255 255 255 / 8%); border-radius: 5px; font-size: 14px;margin-bottom: 10px;">
                        <b>SEO Best Practices:</b> Each page should have <b>one clear H1 tag</b> that defines the main topic. 
                        The H1 should be concise (40-60 characters recommended) and include the primary keyword naturally. 
                        It should be the first heading on the page and remain unique across different pages.  
                        Avoid using multiple H1 tags unless necessary, and ensure it is visible rather than hidden within the code.  
                        A well-structured H1 improves search rankings, enhances readability, and helps search engines understand your content.
                        </div>
                        """, unsafe_allow_html=True)

                        # ✅ Categorize Pages with No H1 or Multiple H1s
                        no_h1_pages = combined_data[combined_data["H1 Count"] == 0]
                        multiple_h1_pages = combined_data[combined_data["H1 Count"] > 1]

                        # ✅ Count the number of affected pages
                        no_h1_count = len(no_h1_pages)
                        multiple_h1_count = len(multiple_h1_pages)

                        # ✅ Display issue counts
                        st.markdown(f"**Pages Missing an H1:** {no_h1_count} | **Pages with Multiple H1s:** {multiple_h1_count}")

                        # ✅ Create a Bar Chart for H1 Issues
                        h1_issue_counts = {
                            "No H1": no_h1_count,
                            "Multiple H1s": multiple_h1_count
                        }
                        fig_h1_issues = px.bar(
                            x=list(h1_issue_counts.keys()), 
                            y=list(h1_issue_counts.values()), 
                            title="Pages with H1 Issues",
                            labels={"x": "H1 Issue Type", "y": "Number of Pages"},
                            color=list(h1_issue_counts.keys()),
                            color_discrete_map={"No H1": "red", "Multiple H1s": "orange"}
                        )
                        st.plotly_chart(fig_h1_issues, use_container_width=True)

                        # ✅ Create Two Columns for Listing Affected Pages
                        col1, col2 = st.columns(2)

                        # Column 1: No H1 Tags
                        with col1:
                            st.subheader(f"Pages Without an H1 Tag ({no_h1_count})")
                            if no_h1_pages.empty:
                                st.success("✅ No pages are missing an H1 tag!")
                            else:
                                st.dataframe(no_h1_pages[["URL", "H1 Count"]])

                        # Column 2: Multiple H1 Tags
                        with col2:
                            st.subheader(f"⚠️ Pages With Multiple H1 Tags ({multiple_h1_count})")
                            if multiple_h1_pages.empty:
                                st.success("✅ No pages have multiple H1 tags!")
                            else:
                                st.dataframe(multiple_h1_pages[["URL", "H1 Count"]])


                    # ✅ Display raw data
                    st.write("Raw Metadata Data")
                    st.dataframe(combined_data[["URL", "SEO Score", "Meta Title", "Title Length", "Meta Description", "Description Length","H1 Present","H1 Count","H1 Text"]])

                else:
                    st.warning("No valid SEO data available for this month.")