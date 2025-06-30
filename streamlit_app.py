import streamlit as st
import pandas as pd
import json
import os
import anthropic

# --- Setup Anthropic Client from env or Streamlit secrets ---
api_key = os.getenv("KIDDOM_ANTHROPIC_API_KEY")
if not api_key:
    api_key = st.secrets.get("KIDDOM_ANTHROPIC_API_KEY")
if not api_key:
    st.error("Anthropic API key not found. Set KIDDOM_ANTHROPIC_API_KEY in your environment or Streamlit secrets.")
    st.stop()

client = anthropic.Anthropic(api_key=api_key)
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("KIDDOM_ANTHROPIC_API_KEY")




# --- Claude-based Scope & Sequence Generation ---
def generate_units_claude(standards_df, sample_units=None, unit_count=None, group_by_theme=False):
    standards_list = [f"{row['id']}: {row['description']}" for _, row in standards_df.iterrows()]
    standards_text = "\n".join(standards_list)

    instruction_parts = []
    if unit_count:
        instruction_parts.append(f"Create exactly {unit_count} instructional units.")
    if group_by_theme:
        instruction_parts.append("Group standards by similar instructional topics or learning themes.")

    instruction_text = "\n".join(instruction_parts)

    if sample_units:
        sample_str = "\n".join([
            f"Unit: {unit['unit_title']}\nStandards: {', '.join(unit['standards'])}\nDescriptions: {'; '.join(unit['descriptions'])}"
            for unit in sample_units
        ])
        system_prompt = f"""
You are a curriculum designer. Use the sample sequence to inspire the new grouping of standards.

Sample:
{sample_str}

Instructions:
{instruction_text}

Group these standards:
{standards_text}

Return JSON output:
[
  {{
    "unit_title": "Name",
    "standards": ["ID1", "ID2"],
    "description": "Text...",
    "duration_weeks": 2
  }}
]
"""
    else:
        system_prompt = f"""
You are a curriculum designer. Group the following standards into instructional units.

Instructions:
{instruction_text}

Group these standards:
{standards_text}

Return JSON output:
[
  {{
    "unit_title": "Name",
    "standards": ["ID1", "ID2"],
    "description": "Text...",
    "duration_weeks": 2
  }}
]
"""

    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=2048,
        temperature=0.4,
        system="You are a curriculum designer.",
        messages=[{"role": "user", "content": system_prompt}]
    )

    content = response.content[0].text
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        st.error("Could not parse Claude's JSON output. Raw content:")
        st.text(content)
        return None

# --- Helper for Sample Unit Map ---
def format_sample_sequence(sample_df, standards_df):
    merged = pd.merge(sample_df, standards_df, on="id", how="left")
    grouped = merged.groupby("unit_title")
    result = []
    for name, group in grouped:
        result.append({
            "unit_title": name,
            "standards": group["id"].tolist(),
            "descriptions": group["description"].tolist()
        })
    return result

# --- Streamlit UI ---
st.title("📚 Scope & Sequence Builder (Claude Edition)")

uploaded_standards = st.file_uploader("Upload standards file (CSV or JSON)", type=["csv", "json"])
uploaded_sample = st.file_uploader("Upload sample unit sequence (optional)", type=["csv", "json"])

st.markdown("### 🛠️ Options")
unit_count = st.slider("Number of units to create", 3, 10, 6)
group_by_theme = st.checkbox("Group by instructional themes", value=True)

if uploaded_standards:
    ext = uploaded_standards.name.split(".")[-1]
    df_standards = pd.read_csv(uploaded_standards) if ext == "csv" else pd.read_json(uploaded_standards)

    if not {"id", "description"}.issubset(df_standards.columns):
        st.error("Standards file must have 'id' and 'description' columns.")
        st.stop()

    st.subheader("📄 Standards Preview")
    st.dataframe(df_standards)

    sample_units = None
    if uploaded_sample:
        ext2 = uploaded_sample.name.split(".")[-1]
        df_sample = pd.read_csv(uploaded_sample) if ext2 == "csv" else pd.read_json(uploaded_sample)
        if not {"id", "unit_title"}.issubset(df_sample.columns):
            st.error("Sample map must contain 'id' and 'unit_title' columns.")
        else:
            st.subheader("🧩 Sample Unit Map")
            st.dataframe(df_sample)
            sample_units = format_sample_sequence(df_sample, df_standards)

    if st.button("🚀 Generate Scope & Sequence"):
        with st.spinner("Calling Claude..."):
            result = generate_units_claude(df_standards, sample_units, unit_count, group_by_theme)
            if result:
                st.success("✅ Scope & Sequence Generated")
                for i, unit in enumerate(result, 1):
                    st.markdown(f"### Unit {i}: {unit['unit_title']}")
                    st.markdown(f"**Duration**: {unit['duration_weeks']} weeks")
                    st.markdown(f"**Description**: {unit['description']}")
                    st.markdown(f"**Standards**: {', '.join(unit['standards'])}")
                    st.markdown("---")

                # CSV download
                df_out = pd.DataFrame(result)
                st.download_button(
                    label="📥 Download as CSV",
                    data=df_out.to_csv(index=False),
                    file_name="scope_sequence.csv",
                    mime="text/csv"
                )
