import streamlit as st
import requests

st.set_page_config(page_title="Image Thumbnail Service", page_icon="🖼️")
st.title("🖼️ Image Thumbnail Service")

base_url = st.text_input(
    "API base URL",
    value=st.session_state.get("base_url", "http://localhost:8000"),
).rstrip("/")
st.session_state["base_url"] = base_url

st.header("1. Upload an image")
uploaded = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png", "webp"])

if uploaded is not None:
    st.image(uploaded, caption=uploaded.name, width=300)
    if st.button("Upload"):
        files = {"files": (uploaded.name, uploaded.getvalue(), uploaded.type)}
        try:
            resp = requests.post(f"{base_url}/v1/images", files=files, timeout=30)
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
        else:
            if resp.status_code == 200:
                image_id = resp.json()["images"][0]["image_id"]
                st.success(f"Uploaded. image_id = `{image_id}`")
                st.session_state["last_image_id"] = image_id
            else:
                st.error(f"{resp.status_code}: {resp.text}")

st.header("2. Create a thumbnail")
image_id = st.text_input("Image ID", value=st.session_state.get("last_image_id", ""))
mode = st.radio("Sizing", ["preset", "custom"], horizontal=True)

if mode == "preset":
    payload = {"preset": st.selectbox("Preset", ["small", "medium", "large"])}
else:
    col1, col2 = st.columns(2)
    payload = {
        "max_width": int(col1.number_input("max_width", min_value=1, value=500)),
        "max_height": int(col2.number_input("max_height", min_value=1, value=500)),
    }

if st.button("Create thumbnail", disabled=not image_id):
    try:
        resp = requests.post(f"{base_url}/v1/images/{image_id}/thumbnails", json=payload, timeout=30)
    except requests.RequestException as exc:
        st.error(f"Request failed: {exc}")
    else:
        if resp.status_code == 200:
            data = resp.json()
            st.success(f"Created thumbnail `{data['thumbnail_id']}` ({data['width']}x{data['height']})")
            thumb_resp = requests.get(
                f"{base_url}/v1/images/{image_id}/thumbnails/{data['thumbnail_id']}", timeout=30
            )
            if thumb_resp.status_code == 200:
                st.image(thumb_resp.content, caption="Thumbnail", width=300)
        else:
            st.error(f"{resp.status_code}: {resp.text}")

st.header("3. Image metadata")
if st.button("Refresh metadata", disabled=not image_id):
    resp = requests.get(f"{base_url}/v1/images/{image_id}", timeout=30)
    if resp.status_code == 200:
        st.json(resp.json())
    else:
        st.error(f"{resp.status_code}: {resp.text}")
