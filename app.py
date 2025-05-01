import streamlit as st
import os
import base64
import json
import time
import tempfile
import requests
from mistralai import Mistral
from pathlib import Path

st.set_page_config(layout="wide", page_title="OCR & Audio App", page_icon="🔊")

# Create tabs for different functions - removed the Write Text tab
tab1, tab2 = st.tabs(["OCR Text Extraction", "Text to Audio Conversion"])

# Function to save file to a specified folder
def save_file(content, filename, folder_path, file_type="binary"):
    try:
        # Create folder if it doesn't exist
        os.makedirs(folder_path, exist_ok=True)
        
        # Full path for the file
        file_path = os.path.join(folder_path, filename)
        
        # Write file content
        if file_type == "text":
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        else:  # binary content
            with open(file_path, 'wb') as f:
                f.write(content)
                
        return True, file_path
    except Exception as e:
        return False, str(e)

with tab1:
    st.title("OCR App")
    st.markdown("<h3 style='color: white;'>Extract text from images and PDFs</h3>", unsafe_allow_html=True)
    
    # 1. API Key Input
    api_key = st.text_input("Enter your Mistral API Key", type="password")
    if not api_key:
        st.info("Please enter your API key to continue.")
        st.stop()

    # Initialize session state variables for persistence
    if "ocr_result" not in st.session_state:
        st.session_state["ocr_result"] = []
    if "preview_src" not in st.session_state:
        st.session_state["preview_src"] = []
    if "image_bytes" not in st.session_state:
        st.session_state["image_bytes"] = []

    # Output folder setting
    output_folder = st.text_input("Output folder path for saved files", 
                                  value=str(Path.home() / "ocr_audio_output"), 
                                  help="Files will be saved to this folder")
    
    # Display verification of folder path
    if os.path.exists(output_folder):
        st.success(f"Folder exists at: {output_folder}")
    else:
        st.warning(f"Folder doesn't exist yet, but will be created when saving files.")
        # Try to create the folder
        try:
            os.makedirs(output_folder, exist_ok=True)
            st.success(f"Successfully created folder at: {output_folder}")
        except Exception as e:
            st.error(f"Unable to create folder: {str(e)}")

    # Horizontal layout for file type and source type
    col1, col2 = st.columns(2)
    
    with col1:
        # 2. Choose file type: PDF or Image
        file_type = st.radio("Select file type", ("PDF", "Image"), horizontal=True)
    
    with col2:
        # 3. Select source type: URL or Local Upload
        source_type = st.radio("Select source type", ("URL", "Local Upload"), horizontal=True)

    # Input based on source type
    if source_type == "URL":
        input_url = st.text_area("Enter one or multiple URLs (separate with new lines)")
        uploaded_files = []
    else:
        uploaded_files = st.file_uploader("Upload one or more files", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)
        input_url = ""

    # 4. Process Button & OCR Handling
    if st.button("Process"):
        if source_type == "URL" and not input_url.strip():
            st.error("Please enter at least one valid URL.")
        elif source_type == "Local Upload" and not uploaded_files:
            st.error("Please upload at least one file.")
        else:
            client = Mistral(api_key=api_key)
            st.session_state["ocr_result"] = []
            st.session_state["preview_src"] = []
            st.session_state["image_bytes"] = []
            
            sources = input_url.split("\n") if source_type == "URL" else uploaded_files
            
            for idx, source in enumerate(sources):
                if file_type == "PDF":
                    if source_type == "URL":
                        document = {"type": "document_url", "document_url": source.strip()}
                        preview_src = source.strip()
                    else:
                        file_bytes = source.read()
                        encoded_pdf = base64.b64encode(file_bytes).decode("utf-8")
                        document = {"type": "document_url", "document_url": f"data:application/pdf;base64,{encoded_pdf}"}
                        preview_src = f"data:application/pdf;base64,{encoded_pdf}"
                else:
                    if source_type == "URL":
                        document = {"type": "image_url", "image_url": source.strip()}
                        preview_src = source.strip()
                    else:
                        file_bytes = source.read()
                        mime_type = source.type
                        encoded_image = base64.b64encode(file_bytes).decode("utf-8")
                        document = {"type": "image_url", "image_url": f"data:{mime_type};base64,{encoded_image}"}
                        preview_src = f"data:{mime_type};base64,{encoded_image}"
                        st.session_state["image_bytes"].append(file_bytes)
                
                with st.spinner(f"Processing {source if source_type == 'URL' else source.name}..."):
                    try:
                        ocr_response = client.ocr.process(model="mistral-ocr-latest", document=document, include_image_base64=True)
                        time.sleep(1)  # wait 1 second between request to prevent rate limit exceeding
                        
                        pages = ocr_response.pages if hasattr(ocr_response, "pages") else (ocr_response if isinstance(ocr_response, list) else [])
                        result_text = "\n\n".join(page.markdown for page in pages) or "No result found."
                    except Exception as e:
                        result_text = f"Error extracting result: {e}"
                    
                    st.session_state["ocr_result"].append(result_text)
                    st.session_state["preview_src"].append(preview_src)

    # 5. Display Preview and OCR Results if available
    if st.session_state["ocr_result"]:
        for idx, result in enumerate(st.session_state["ocr_result"]):
            st.markdown("---")
            st.subheader(f"Result {idx+1}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                file_type_label = "PDF" if file_type == "PDF" else "Image"
                st.subheader(f"Input {file_type_label}")
                if file_type == "PDF":
                    pdf_embed_html = f'<iframe src="{st.session_state["preview_src"][idx]}" width="100%" height="400" frameborder="0"></iframe>'
                    st.markdown(pdf_embed_html, unsafe_allow_html=True)
                else:
                    if source_type == "Local Upload" and idx < len(st.session_state["image_bytes"]):
                        st.image(st.session_state["image_bytes"][idx])
                    else:
                        st.image(st.session_state["preview_src"][idx])
            
            with col2:
                st.subheader("OCR Results")
                
                # Show results in a text area that can be edited
                edited_text = st.text_area(
                    "Extracted text (you can edit this)",
                    value=result,
                    height=300,
                    key=f"result_text_{idx}"
                )
                
                # Update the session state with any edits
                st.session_state["ocr_result"][idx] = edited_text
                
                # Horizontal layout for buttons
                btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                
                with btn_col1:
                    # JSON download
                    json_data = json.dumps({"ocr_result": edited_text}, ensure_ascii=False, indent=2)
                    json_b64 = base64.b64encode(json_data.encode()).decode()
                    st.markdown(
                        f'<a href="data:application/json;base64,{json_b64}" download="Output_{idx+1}.json">Download JSON</a>',
                        unsafe_allow_html=True
                    )
                
                with btn_col2:
                    # Text download
                    text_b64 = base64.b64encode(edited_text.encode()).decode()
                    st.markdown(
                        f'<a href="data:text/plain;base64,{text_b64}" download="Output_{idx+1}.txt">Download Text</a>',
                        unsafe_allow_html=True
                    )
                
                with btn_col3:
                    # Save JSON to folder
                    if st.button(f"Save JSON to Folder", key=f"save_json_{idx}"):
                        json_data = json.dumps({"ocr_result": edited_text}, ensure_ascii=False, indent=2)
                        success, result_path = save_file(
                            json_data, 
                            f"Output_{idx+1}.json", 
                            output_folder,
                            file_type="text"
                        )
                        if success:
                            st.success(f"JSON saved to: {result_path}")
                            # Verify if file exists
                            if os.path.exists(result_path):
                                st.success(f"✓ Verified: File exists at {result_path}")
                            else:
                                st.error(f"✗ File not found at {result_path}")
                        else:
                            st.error(f"Failed to save JSON: {result_path}")
                
                with btn_col4:
                    # Save Text to folder
                    if st.button(f"Save Text to Folder", key=f"save_text_{idx}"):
                        success, result_path = save_file(
                            edited_text, 
                            f"Output_{idx+1}.txt", 
                            output_folder,
                            file_type="text"
                        )
                        if success:
                            st.success(f"Text saved to: {result_path}")
                            # Verify if file exists
                            if os.path.exists(result_path):
                                st.success(f"✓ Verified: File exists at {result_path}")
                            else:
                                st.error(f"✗ File not found at {result_path}")
                        else:
                            st.error(f"Failed to save text: {result_path}")
                
                # Button to convert this specific result to audio
                if st.button(f"Convert to Audio", key=f"convert_btn_{idx}"):
                    # Store this specific text in session state for the audio tab
                    st.session_state["current_text_for_audio"] = edited_text
                    # Switch to the audio tab
                    st.info("Text ready for conversion. Please go to the 'Text to Audio Conversion' tab.")

# Text to Audio Tab
with tab2:
    st.title("Text to Audio Converter")
    
    # OpenAI API Key
    openai_api_key = st.text_input("Enter your OpenAI API Key", type="password", key="openai_key")
    
    # Output folder setting (shared with OCR tab)
    if "output_folder" in locals():
        audio_output_folder = st.text_input("Output folder path for saved files", 
                      value=output_folder,
                      help="Files will be saved to this folder",
                      key="audio_output_folder")
    else:
        audio_output_folder = st.text_input("Output folder path for saved files", 
                                      value=str(Path.home() / "ocr_audio_output"),
                                      help="Files will be saved to this folder",
                                      key="audio_output_folder")
    
    # Display verification of folder path
    if os.path.exists(audio_output_folder):
        st.success(f"Folder exists at: {audio_output_folder}")
    else:
        st.warning(f"Folder doesn't exist yet, but will be created when saving files.")
        try:
            os.makedirs(audio_output_folder, exist_ok=True)
            st.success(f"Successfully created folder at: {audio_output_folder}")
        except Exception as e:
            st.error(f"Unable to create folder: {str(e)}")
    
    # Horizontal layout for source and voice
    col1, col2 = st.columns(2)
    
    with col1:
        # Method selection - adjusted options since there's no Write tab
        text_source = st.radio("Text source", ["OCR results", "Direct input", "Upload file"], horizontal=True)
    
    with col2:
        # Voice selection
        voice_option = st.selectbox(
            "Select voice style",
            ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        )
    
    text_for_audio = ""
    
    if text_source == "OCR results":
        # Show dropdown of available OCR results
        if st.session_state.get("ocr_result", []):
            result_options = [f"Result {i+1}" for i in range(len(st.session_state["ocr_result"]))]
            
            # If we have a current text from button click, pre-select it
            default_idx = 0
            if "current_text_for_audio" in st.session_state:
                try:
                    default_idx = st.session_state["ocr_result"].index(st.session_state["current_text_for_audio"])
                except ValueError:
                    default_idx = 0
            
            selected_result = st.selectbox(
                "Select OCR result to convert",
                result_options,
                index=default_idx
            )
            
            # Get the index from the selected option
            result_idx = result_options.index(selected_result)
            text_for_audio = st.session_state["ocr_result"][result_idx]
            
            # Display the text in a text area that can be edited
            text_for_audio = st.text_area(
                "OCR text (you can edit before converting)",
                value=text_for_audio,
                height=300
            )
        else:
            st.warning("No OCR results available. Process files in the OCR tab first or choose another source.")
    
    elif text_source == "Direct input":
        # Let user enter text directly
        text_for_audio = st.text_area(
            "Enter text to convert to audio",
            value="",
            height=300
        )
    
    else:  # Upload file
        uploaded_text_file = st.file_uploader("Upload a text file", type=["txt", "md"])
        if uploaded_text_file:
            text_content = uploaded_text_file.read().decode("utf-8")
            text_for_audio = st.text_area(
                "Text from file (you can edit before converting)",
                value=text_content,
                height=300
            )
    
    # Function to convert text to audio
    def convert_text_to_speech(text, api_key, voice="alloy"):
        try:
            # Prepare the API request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # OpenAI's TTS endpoint
            url = "https://api.openai.com/v1/audio/speech"
            
            data = {
                "model": "tts-1",
                "input": text,
                "voice": voice
            }
            
            # Send the request to the TTS API
            response = requests.post(url, headers=headers, json=data)
            
            # Check if the request was successful
            if response.status_code == 200:
                # Save the audio to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name
                
                return True, temp_file_path, response.content
            else:
                return False, f"API Error: {response.status_code}, {response.text}", None
        
        except Exception as e:
            return False, f"Error: {str(e)}", None
    
    # Initialize audio results in session state
    if "audio_results" not in st.session_state:
        st.session_state["audio_results"] = []
    
    # Generate button
    if st.button("Generate Audio"):
        if not openai_api_key:
            st.error("Please enter your OpenAI API Key.")
        elif not text_for_audio:
            st.error("Please provide text to convert to audio.")
        else:
            with st.spinner("Converting text to audio..."):
                success, audio_path, audio_content = convert_text_to_speech(
                    text_for_audio, 
                    openai_api_key,
                    voice=voice_option
                )
                
                if success:
                    # Store in session state
                    st.session_state["audio_results"].append({
                        "text": text_for_audio[:100] + "..." if len(text_for_audio) > 100 else text_for_audio,
                        "path": audio_path,
                        "content": audio_content,
                        "voice": voice_option
                    })
                    
                    st.success("Audio generated successfully!")
                else:
                    st.error(f"Error generating audio: {audio_path}")
    
    # Display audio results
    if st.session_state["audio_results"]:
        st.subheader("Generated Audio Files")
        
        for idx, audio_data in enumerate(st.session_state["audio_results"]):
            with st.expander(f"Audio {idx+1} - {audio_data['voice']}", expanded=(idx == len(st.session_state["audio_results"])-1)):
                # Show text snippet
                st.markdown(f"**Text:** {audio_data['text']}")
                
                # Audio player
                st.audio(audio_data["path"])
                
                # Two columns for download options
                dl_col1, dl_col2 = st.columns(2)
                
                with dl_col1:
                    # Download link for audio
                    audio_b64 = base64.b64encode(audio_data["content"]).decode()
                    audio_href = f'<a href="data:audio/mp3;base64,{audio_b64}" download="Audio_{idx+1}.mp3">Download Audio File</a>'
                    st.markdown(audio_href, unsafe_allow_html=True)
                
                with dl_col2:
                    # Save audio to folder
                    if st.button(f"Save Audio to Folder", key=f"save_audio_{idx}"):
                        # Generate a filename based on text content
                        text_preview = audio_data["text"][:20].replace(" ", "_")
                        filename = f"Audio_{idx+1}_{text_preview}.mp3"
                        
                        success, result_path = save_file(
                            audio_data["content"],
                            filename,
                            audio_output_folder
                        )
                        
                        if success:
                            st.success(f"Audio saved to: {result_path}")
                            # Verify if file exists
                            if os.path.exists(result_path):
                                st.success(f"✓ Verified: File exists at {result_path}")
                            else:
                                st.error(f"✗ File not found at {result_path}")
                        else:
                            st.error(f"Failed to save audio: {result_path}")

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888888;">
    <p>Built with Mistral OCR and OpenAI Text-to-Speech</p>
</div>
""", unsafe_allow_html=True)