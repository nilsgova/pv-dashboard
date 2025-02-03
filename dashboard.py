import boto3
import pandas as pd
import streamlit as st
import plotly.express as px
from io import BytesIO
import gzip
import logging

# ✅ Streamlit Page Configuration (Must be First)
st.set_page_config(page_title="Multi-Dashboard", layout="wide")

# ✅ AWS S3 Configuration
AWS_BUCKET_NAME = "pv-monthly-reports"
AWS_REGION = "eu-central-1"

# ✅ Initialize S3 Client (Only Once)
if "s3_client" not in st.session_state:
    st.session_state.s3_client = boto3.client("s3", region_name=AWS_REGION)

# ✅ Function to List S3 Files (Checks Session Cache First)
def list_s3_files(prefix):
    """List all files in S3 bucket with a given prefix, using session cache."""
    if prefix not in st.session_state:
        logging.info(f"🔄 Fetching fresh file list from S3 for: {prefix}")
        response = st.session_state.s3_client.list_objects_v2(Bucket=AWS_BUCKET_NAME, Prefix=prefix)
        st.session_state[prefix] = [
            obj["Key"]
            for obj in response.get("Contents", [])
            if obj["Key"].endswith(".csv.gz")
        ]
    return st.session_state[prefix]

# ✅ Function to Read S3 CSV GZIP (Checks Session Cache First)
def read_s3_csv_gzip(file_key):
    """Read a compressed CSV (GZIP) file from S3 into a Pandas DataFrame, using session cache."""
    if file_key not in st.session_state:
        logging.info(f"🔄 Fetching fresh data from S3 for: {file_key}")
        obj = st.session_state.s3_client.get_object(Bucket=AWS_BUCKET_NAME, Key=file_key)
        with gzip.GzipFile(fileobj=BytesIO(obj["Body"].read()), mode='rb') as f:
            st.session_state[file_key] = pd.read_csv(f)
    return st.session_state[file_key]

# ✅ Only Fetch File Lists If Not Already Stored
if "accessibility_files" not in st.session_state:
    st.session_state.accessibility_files = sorted(list_s3_files("accessibility_report_"))
if "broken_links_files" not in st.session_state:
    st.session_state.broken_links_files = sorted(list_s3_files("broken_links_report_"))
if "seo_files" not in st.session_state:
    st.session_state.seo_files = sorted(list_s3_files("seo_report_"))

# ✅ Use Cached File Lists
accessibility_files = st.session_state.accessibility_files
broken_links_files = st.session_state.broken_links_files
seo_files = st.session_state.seo_files

# ✅ Preload all data once per session
if "preloaded_accessibility_data" not in st.session_state:
    st.session_state.preloaded_accessibility_data = {
        f: read_s3_csv_gzip(f) for f in accessibility_files
    }
if "preloaded_broken_links_data" not in st.session_state:
    st.session_state.preloaded_broken_links_data = {
        f: read_s3_csv_gzip(f) for f in broken_links_files
    }
if "preloaded_seo_data" not in st.session_state:
    st.session_state.preloaded_seo_data = {f: read_s3_csv_gzip(f) for f in seo_files}

# ✅ Use Cached Data
preloaded_accessibility_data = st.session_state.preloaded_accessibility_data
preloaded_broken_links_data = st.session_state.preloaded_broken_links_data
preloaded_seo_data = st.session_state.preloaded_seo_data

# ✅ Streamlit UI
st.title("P&V Analysis Dashboard")
main_tabs = st.tabs(["Accessibility", "Broken Links", "SEO"])

### ✅ Accessibility Tab ###
with main_tabs[0]:
    st.header("Accessibility Dashboard")

    if not accessibility_files:
        st.warning("No Accessibility reports found.")
    else:
        # Extract months from the filenames (format: accessibility_report_YYYY-MM-DD.csv.gz)
        months = sorted(set([f.split("_")[2][:7] for f in accessibility_files]))
        tabs = st.tabs(months)

        for i, month in enumerate(months):
            with tabs[i]:
                st.subheader(f"Accessibility Data for {month}")

                # Load and combine data for the month
                month_files = [f for f in accessibility_files if f.split("_")[2].startswith(month)]
                combined_data = pd.concat([preloaded_accessibility_data[f] for f in month_files])

                # ✅ Impact Distribution (Bar Chart)
                st.subheader("Impact Distribution")
                total_pages = len(
                    st.session_state.preloaded_seo_data[
                        list(st.session_state.preloaded_seo_data.keys())[0]
                    ]["Original Url"]
                )
                st.write(f"Total Pages Scanned: {total_pages}")
                desired_order = ["critical", "serious", "moderate", "minor"]
                impact_counts = combined_data["Impact"].value_counts().reindex(desired_order, fill_value=0)
                impact_counts_df = impact_counts.reset_index()
                impact_counts_df.columns = ["Impact", "Count"]

                color_map = {"critical": "red", "serious": "orange", "moderate": "yellow", "minor": "green"}

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

                # Create Impact Tabs for detailed view
                impact_tabs = st.tabs(["Critical", "Serious", "Moderate", "Minor"])

                for j, impact_level in enumerate(desired_order):
                    with impact_tabs[j]:
                        st.subheader(f"{impact_level.capitalize()} Violations")
                        impact_data = combined_data[combined_data["Impact"] == impact_level]

                        if impact_data.empty:
                            st.success(f"✅ No {impact_level} violations found!")
                        else:
                            violation_counts = impact_data["Violation ID"].value_counts().reset_index()
                            violation_counts.columns = ["Violation ID", "Count"]

                            selected_violation = st.selectbox(
                                "Select a Violation ID:",
                                violation_counts["Violation ID"],
                                format_func=lambda x: f"{x} ({violation_counts[violation_counts['Violation ID'] == x]['Count'].values[0]} occurrences)"
                            )

                            violation_details = impact_data[impact_data["Violation ID"] == selected_violation].iloc[0]
                            st.markdown(f"""
                                **Violation Description:** {violation_details["Description"]}
                                
                                **Recommendation:** {violation_details["Recommendation"]}
                            """)

                            st.markdown("#### Affected URLs")
                            violation_urls = impact_data[impact_data["Violation ID"] == selected_violation][["URL", "Element", "Location"]]
                            st.dataframe(violation_urls)

                # Display Raw Data
                st.write("Raw Data")
                st.dataframe(combined_data)

### ✅ Broken Links Tab ###
with main_tabs[1]:
    st.header("Broken Links Dashboard")

    if not broken_links_files:
        st.warning("No Broken Links reports found.")
    else:
        # Extract months from the broken links filenames.
        # Expected format: broken_links_report_YYYY-MM-DD.csv.gz
        months = sorted(set([f.split("_")[3].split(".")[0][:7] for f in broken_links_files]))
        tabs = st.tabs(months)
        
        for i, month in enumerate(months):
            with tabs[i]:
                st.subheader(f"Broken Links Data for {month}")
                
                # Filter the broken_links_files to only include files for this month
                month_files = [
                    f for f in broken_links_files
                    if f.split("_")[3].split(".")[0].startswith(month)
                ]
                
                if month_files:
                    valid_files = [
                        preloaded_broken_links_data[f]
                        for f in month_files
                        if not preloaded_broken_links_data[f].empty
                    ]
                    
                    if valid_files:
                        combined_data = pd.concat(valid_files)
                        st.write("Raw Data")
                        st.dataframe(combined_data)
                    else:
                        st.warning("No valid Broken Links data available for this month.")
                else:
                    st.warning("No Broken Links data available for this month.")


### ✅ SEO Tab ###
with main_tabs[2]:
    st.header("SEO Dashboard")

    if not seo_files:
        st.warning("No SEO reports found.")
    else:
        # Extract months from the SEO filenames (format: seo_report_YYYY-MM-DD.csv.gz)
        months = sorted(set([f.split("_")[2][:7] for f in seo_files]))
        tabs = st.tabs(months)

        for i, month in enumerate(months):
            with tabs[i]:
                month_files = [f for f in seo_files if f.split("_")[2].startswith(month)]
                valid_files = [f for f in month_files]
                total_pages = len(
                    st.session_state.preloaded_seo_data[
                        list(st.session_state.preloaded_seo_data.keys())[0]
                    ]["Original Url"]
                )
                st.write(f"Total Pages Scanned: {total_pages}")

                if valid_files:
                    try:
                        combined_data = pd.concat([preloaded_seo_data[f] for f in valid_files])

                        # ✅ Ensure required columns exist
                        expected_columns = ["SEO Score", "Title 1 Length", "Meta Description 1 Length"]
                        for col in expected_columns:
                            if col not in combined_data.columns:
                                st.warning(f"⚠️ Missing column: {col}. Check data format.")
                                st.stop()

                        combined_data["SEO Score"] = pd.to_numeric(combined_data["SEO Score"], errors="coerce")
                        combined_data.dropna(subset=["SEO Score"], inplace=True)

                        # ✅ SEO Score Categorization
                        bins = [0, 49, 69, 79, 89, 100]
                        labels = ["Very Bad (0-49)", "Bad (50-69)", "Average (70-79)", "Good (80-89)", "Very Good (90-100)"]
                        combined_data["SEO Category"] = pd.cut(combined_data["SEO Score"], bins=bins, labels=labels, include_lowest=True)

                        with st.expander("📌 SEO Score Analysis"):
                            st.subheader("SEO Score Analysis")
                            st.markdown("""
                            <div style="padding: 8px; background-color: rgb(255 255 255 / 8%); border-radius: 5px; font-size: 14px;">
                            The SEO Score is a calculated metric that evaluates how well a webpage follows <b>best practices</b> for 
                            <b>search engine optimization (SEO)</b>. <br/>It is a <b>0-100 scale</b>, where higher scores indicate 
                            <b>better optimization</b>. The score is based on multiple factors that impact <b>indexability</b>, 
                            <b>content structure</b>, <b>metadata</b>, <b>performance</b>, and <b>technical SEO</b>.
                            </div>
                            """, unsafe_allow_html=True)

                            seo_category_counts = combined_data["SEO Category"].value_counts().reindex(labels, fill_value=0)

                            fig_seo = px.bar(
                                seo_category_counts.reset_index(),
                                y="SEO Category",
                                x=seo_category_counts.values,
                                title="SEO Score Distribution",
                                labels={"x": "Number of Pages", "SEO Category": "SEO Score Category"},
                                orientation="h",
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
                            
                            score_tabs = st.tabs(labels)

                            for j, category in enumerate(labels):
                                with score_tabs[j]:
                                    category_data = combined_data[combined_data["SEO Category"] == category]

                                    if category_data.empty:
                                        st.warning(f"No pages in the {category} category.")
                                    else:
                                        st.subheader(f"Pages in {category} Category")
                                        st.write(f"Total pages: **{len(category_data)}**")

                                        category_data_sorted = category_data.sort_values(by="SEO Score", ascending=True)

                                        st.dataframe(category_data_sorted[["Original Url", "SEO Score"]])
                        with st.expander("📌 HTTP Status Codes Issues"):
                            st.subheader("HTTP Status Codes Issues")
                            combined_data["Indexability Status"] = combined_data["Indexability Status"].astype(str).fillna("Unknown")
                            filtered_data = combined_data[~combined_data["Indexability Status"].isin(["nan", "Unknown"])]
                            canonical_counts = filtered_data["Indexability Status"].value_counts()

                            if canonical_counts.empty:
                                st.success("✅ No Canonicalization Issues Found!")
                            else:
                                fig_canonical = px.bar(
                                    x=canonical_counts.index,
                                    y=canonical_counts.values,
                                    title="Canonicalization Issues",
                                    labels={"x": "Canonicalization Status", "y": "Number of Pages"},
                                    color=canonical_counts.index,
                                    color_discrete_map={"Canonicalised": "green", "Redirected": "orange", "Duplicate": "red"},
                                )
                                st.plotly_chart(fig_canonical, use_container_width=True)

                                st.subheader("Canonicalization Issues Breakdown")

                                canonicalization_issues = sorted([(issue, count) for issue, count in canonical_counts.items()])

                                if not canonicalization_issues:
                                    st.success("✅ No Canonicalization Issues Found!")
                                else:
                                    issue_tabs = st.tabs([f"{issue} ({count})" for issue, count in canonicalization_issues])

                                    for k, (issue, count) in enumerate(canonicalization_issues):
                                        with issue_tabs[k]:
                                            st.subheader(f"Pages with '{issue}' Issue ({count})")
                                            issue_data = filtered_data[filtered_data["Indexability Status"] == issue]

                                            if issue_data.empty:
                                                st.success(f"✅ No pages have the '{issue}' issue!")
                                            else:
                                                if issue.lower() == "redirected" and "Redirect URL" in issue_data.columns:
                                                    st.dataframe(issue_data[["Original Url", "Status Code", "Redirect URL"]])
                                                else:
                                                    st.dataframe(issue_data[["Original Url"]])
                        with st.expander("📌 Meta Data Analysis"):
                            st.subheader("Meta Data Analysis")
                            combined_data["Title 1"] = combined_data["Title 1"].fillna("").replace("", "Missing")
                            combined_data["Meta Description 1"] = combined_data["Meta Description 1"].fillna("").replace("", "Missing")
                            meta_title_counts = combined_data["Title 1"].apply(lambda x: "Missing" if x == "Missing" else "Present").value_counts()
                            meta_desc_counts = combined_data["Meta Description 1"].apply(lambda x: "Missing" if x == "Missing" else "Present").value_counts()
                            meta_title_counts = meta_title_counts.reindex(["Present", "Missing"], fill_value=0)
                            meta_desc_counts = meta_desc_counts.reindex(["Present", "Missing"], fill_value=0)
                            fig_meta_desc = px.pie(
                                names=meta_desc_counts.index, values=meta_desc_counts.values,
                                title="Meta Description Presence",
                                color_discrete_sequence=["purple", "orange"]
                            )
                            fig_meta_title = px.pie(
                                names=meta_title_counts.index, values=meta_title_counts.values,
                                title="Meta Title Presence",
                                color_discrete_sequence=["blue", "red"]
                            )
                            col1, col2 = st.columns(2)
                            with col1:
                                st.plotly_chart(fig_meta_title, use_container_width=True)
                            with col2:
                                st.plotly_chart(fig_meta_desc, use_container_width=True)

                            title_too_short = combined_data[
                                (combined_data["Title 1 Length"] < 30) | (combined_data["Title 1 Length"] == 0)
                            ]
                            title_too_long = combined_data[combined_data["Title 1 Length"] > 60]

                            description_too_short = combined_data[
                                (combined_data["Meta Description 1 Length"] < 50) | (combined_data["Meta Description 1 Length"] == 0)
                            ]
                            description_too_long = combined_data[combined_data["Meta Description 1 Length"] > 160]

                            col1, col2 = st.columns(2)

                            with col1:
                                st.subheader("Pages with Title Length Issues")
                                st.markdown("""
                                <div style="padding: 8px; background-color: rgb(255 255 255 / 8%); border-radius: 5px; font-size: 14px;">
                                <b>SEO Best Practices:</b> Titles should be between <b>50-60 characters</b> for optimal visibility. 
                                Short titles may lack enough context, while long titles can get <b>cut off</b> in search results.
                                </div>
                                """, unsafe_allow_html=True)

                                short_title_count = len(title_too_short)
                                long_title_count = len(title_too_long)

                                st.markdown(f"#### **Too Short Titles ({short_title_count})**")
                                if title_too_short.empty:
                                    st.success("✅ No titles are too short!")
                                else:
                                    st.dataframe(title_too_short[["Original Url", "Title 1", "Title 1 Length"]])

                                st.markdown(f"#### **Too Long Titles ({long_title_count})**")
                                if title_too_long.empty:
                                    st.success("✅ No titles are too long!")
                                else:
                                    st.dataframe(title_too_long[["Original Url", "Title 1", "Title 1 Length"]])
                            with col2:
                                st.subheader("Pages with Description Length Issues")
                                st.markdown("""
                                <div style="padding: 8px; background-color: rgb(255 255 255 / 8%); border-radius: 5px; font-size: 14px;">
                                <b>SEO Best Practices:</b> Meta descriptions should be between <b>50-160 characters</b>. 
                                A well-written description can **increase click-through rates**, while too long descriptions may be <b>truncated</b>.
                                </div>
                                """, unsafe_allow_html=True)

                                short_desc_count = len(description_too_short)
                                long_desc_count = len(description_too_long)

                                st.markdown(f"#### **Too Short Descriptions ({short_desc_count})**")
                                if description_too_short.empty:
                                    st.success("✅ No descriptions are too short!")
                                else:
                                    st.dataframe(description_too_short[["Original Url", "Meta Description 1", "Meta Description 1 Length"]])

                                st.markdown(f"#### **Too Long Descriptions ({long_desc_count})**")
                                if description_too_long.empty:
                                    st.success("✅ No descriptions are too long!")
                                else:
                                    st.dataframe(description_too_long[["Original Url", "Meta Description 1", "Meta Description 1 Length"]])
                        with st.expander("📌 H1 Tag Issues Overview"):
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

                            required_cols = ["H1-1", "H1-2", "Status Code"]
                            for col in required_cols:
                                if col not in combined_data.columns:
                                    st.warning(f"⚠️ Missing column: {col}. Check data format.")
                                    st.stop()

                            combined_data["Status Code"] = pd.to_numeric(combined_data["Status Code"], errors="coerce")
                            non_redirected_data = combined_data[~combined_data["Status Code"].between(300, 399, inclusive="both")]

                            non_redirected_data["H1-1"] = non_redirected_data["H1-1"].fillna("").astype(str)
                            non_redirected_data["H1-2"] = non_redirected_data["H1-2"].fillna("").astype(str)

                            no_h1_pages = non_redirected_data[non_redirected_data["H1-1"] == ""]
                            multiple_h1_pages = non_redirected_data[
                                (non_redirected_data["H1-1"] != "") & (non_redirected_data["H1-2"] != "")
                            ]

                            no_h1_count = len(no_h1_pages)
                            multiple_h1_count = len(multiple_h1_pages)

                            st.markdown(f"**Pages Missing an H1:** {no_h1_count} | **Pages with Multiple H1s:** {multiple_h1_count}")

                            h1_issue_counts = {"No H1": no_h1_count, "Multiple H1s": multiple_h1_count}
                            fig_h1_issues = px.bar(
                                x=list(h1_issue_counts.keys()),
                                y=list(h1_issue_counts.values()),
                                title="Pages with H1 Issues (Excluding Redirected Pages)",
                                labels={"x": "H1 Issue Type", "y": "Number of Pages"},
                                color=list(h1_issue_counts.keys()),
                                color_discrete_map={"No H1": "red", "Multiple H1s": "orange"}
                            )
                            st.plotly_chart(fig_h1_issues, use_container_width=True)

                            col1, col2 = st.columns(2)

                            with col1:
                                st.subheader(f"Pages Without an H1 Tag ({no_h1_count})")
                                if no_h1_pages.empty:
                                    st.success("✅ No pages are missing an H1 tag!")
                                else:
                                    st.dataframe(no_h1_pages[["Original Url", "H1-1"]])
                            with col2:
                                st.subheader(f"Pages With Multiple H1 Tags ({multiple_h1_count})")
                                if multiple_h1_pages.empty:
                                    st.success("✅ No pages have multiple H1 tags!")
                                else:
                                    st.dataframe(multiple_h1_pages[["Original Url", "H1-1", "H1-2"]])

                        st.write("Raw Metadata Data")
                        st.dataframe(
                            combined_data[
                                [
                                    "Original Url",
                                    "Address",
                                    "Content Type",
                                    "Status Code",
                                    "Status",
                                    "Indexability",
                                    "Indexability Status",
                                    "Title 1",
                                    "Title 1 Length",
                                    "Title 1 Pixel Width",
                                    "Meta Description 1",
                                    "Meta Description 1 Length",
                                    "Meta Description 1 Pixel Width",
                                    "Meta Keywords 1",
                                    "Meta Keywords 1 Length",
                                    "H1-1",
                                    "H1-1 Length",
                                    "H1-2",
                                    "H1-2 Length",
                                    "H2-1",
                                    "H2-1 Length",
                                    "H2-2",
                                    "H2-2 Length",
                                    "Meta Robots 1",
                                    "X-Robots-Tag 1",
                                    "Meta Refresh 1",
                                    "Canonical Link Element 1",
                                ]
                            ]
                        )
                    except Exception as e:
                        st.error(f"❌ Error loading SEO data: {e}")
                else:
                    st.warning("No valid SEO data available for this month.")
