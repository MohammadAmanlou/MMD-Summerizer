import streamlit as st
from transformers import SeamlessM4TModel, AutoProcessor
from transformers import MarianMTModel, MarianTokenizer  
from transformers import T5ForConditionalGeneration, T5Tokenizer
import torch
import langid
import requests
from transformers import pipeline
from rouge import Rouge
from nltk.translate.bleu_score import sentence_bleu
from bert_score import score as bert_score
import nltk

nltk.download('punkt')

# Hugging Face API URL and headers
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": "Bearer YOUR_API_KEY_HERE"}  # Replace with your actual API key

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

def summarize_text(text, min_length, max_length):
    payload = {
        "inputs": text,
        "parameters": {
            "min_length": min_length,
            "max_length": max_length
        }
    }
    output = query(payload)

    if isinstance(output, list) and len(output) > 0:
        return output[0]['summary_text']
    else:
        return "Error: Unable to get a summary."

def summarize(text, min_length, max_length):
    max_input_length = 1024

    if len(text.split()) > max_input_length:
        text = ' '.join(text.split()[:max_input_length])
        st.warning("Input text was too long and has been truncated.")

    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

    try:
        summary = summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        st.error(f"An error occurred during summarization: {str(e)}")
        return None

def evaluate_summary(reference, summary):
    metrics = {}

    rouge = Rouge()
    rouge_scores = rouge.get_scores(summary, reference, avg=True)
    metrics['ROUGE-1'] = rouge_scores['rouge-1']['f']
    metrics['ROUGE-2'] = rouge_scores['rouge-2']['f']
    metrics['ROUGE-L'] = rouge_scores['rouge-l']['f']

    reference_tokens = [nltk.word_tokenize(reference)]
    summary_tokens = nltk.word_tokenize(summary)
    metrics['BLEU'] = sentence_bleu(reference_tokens, summary_tokens)

    P, R, F1 = bert_score([summary], [reference], lang="en")
    metrics['BERTScore (F1)'] = F1.mean().item()

    return metrics

def translate_text(input_text, output_language="fra", model_index=0):
    try:
        input_language, _ = langid.classify(input_text)

        model_choices = [
            "facebook/hf-seamless-m4t-medium",
            "Helsinki-NLP/opus-mt-en-roa",
            "google/madlad400-10b-mt"
        ]

        model_name = model_choices[model_index]

        if model_index == 0:
            model = SeamlessM4TModel.from_pretrained(model_name)
            processor = AutoProcessor.from_pretrained(model_name)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model.to(device)
            inputs = processor(text=input_text, src_lang=input_language, return_tensors="pt").to(device)
            with torch.no_grad():
                outputs = model.generate(**inputs, tgt_lang=output_language, generate_speech=False)
            translated_text = processor.decode(outputs[0].tolist()[0], skip_special_tokens=True)

        elif model_index == 1:
            # MarianMT
            tokenizer = MarianTokenizer.from_pretrained(model_name)
            model = MarianMTModel.from_pretrained(model_name)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model.to(device)
            # Properly tokenize the input text
            input_tokens = tokenizer(input_text, return_tensors="pt", padding=True).to(device)
            translated = model.generate(input_ids=input_tokens["input_ids"], attention_mask=input_tokens["attention_mask"])
            translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)

        elif model_index == 2:
            # MADLAD400
            model = T5ForConditionalGeneration.from_pretrained(model_name)
            tokenizer = T5Tokenizer.from_pretrained(model_name)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model.to(device)
            text = f"<2{output_language}>{input_text}"
            # Properly tokenize the input text
            input_ids = tokenizer(text, return_tensors="pt").input_ids.to(device)
            outputs = model.generate(input_ids=input_ids)
            translated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        return translated_text

    except Exception as e:
        st.error(f"An error occurred during translation: {str(e)}")
        return None


# Streamlit app
st.title("MMD Summarizer with Translation")

# Initialize session state
if 'stage' not in st.session_state:
    st.session_state.stage = 'selection'
    st.session_state.text = ''
    st.session_state.summary = ''
    st.session_state.translated_text = ''

# Stage: Operation Selection
if st.session_state.stage == 'selection':
    text = st.text_area("Enter your text:")
    operation = st.selectbox("Select the desired operation:", 
                             ["Summarization only", "Translation only", "Summarization before Translation", "Translation before Summarization"])

    if st.button("Continue"):
        if not text.strip():
            st.error("Please enter some text.")
        else:
            st.session_state.text = text
            if operation == "Summarization only":
                st.session_state.stage = 'summarization'
            elif operation == "Translation only":
                st.session_state.stage = 'translation'
            elif operation == "Summarization before Translation":
                st.session_state.stage = 'summarization_before_translation'
            elif operation == "Translation before Summarization":
                st.session_state.stage = 'translation_before_summarization'
            st.session_state.operation = operation

# Stage: Only Summarization
if st.session_state.stage == 'summarization':
    st.subheader("Summarization Settings")
    min_length = st.number_input("Minimum summary length (words):", min_value=5, max_value=500, value=50)
    max_length = st.number_input("Maximum summary length (words):", min_value=min_length, max_value=1000, value=100)

    if st.button("Summarize"):
        summary = summarize(st.session_state.text, min_length=min_length, max_length=max_length)
        if summary:
            st.write("**Summary:**")
            st.write(summary)
            print("Summary evaluation (in terminal):")
            metrics = evaluate_summary(st.session_state.text, summary)
            print(f"ROUGE-1: {metrics['ROUGE-1']:.4f}")
            print(f"ROUGE-2: {metrics['ROUGE-2']:.4f}")
            print(f"ROUGE-L: {metrics['ROUGE-L']:.4f}")
            print(f"BLEU: {metrics['BLEU']:.4f}")
            print(f"BERTScore (F1): {metrics['BERTScore (F1)']:.4f}")
            st.session_state.stage = 'done'

# Stage: Only Translation
if st.session_state.stage == 'translation':
    st.subheader("Translation Settings")
    output_language = st.text_input("Enter the target language code (e.g., 'fa' for Persian):", value="fa")
    model_option = st.selectbox("Select the translation model:", 
                                ["SeamlessM4T", "Opus-MT", "MADLAD400"])
    model_index = ["SeamlessM4T", "Opus-MT", "MADLAD400"].index(model_option)

    if st.button("Translate"):
        translated_text = translate_text(st.session_state.text, output_language, model_index)
        if translated_text:
            st.write("**Translated Text:**")
            st.write(translated_text)
            st.session_state.stage = 'done'

# Stage: Summarization before Translation
if st.session_state.stage == 'summarization_before_translation':
    st.subheader("Summarization Settings")
    min_length = st.number_input("Minimum summary length (words):", min_value=5, max_value=500, value=50, key='sbt_min_length')
    max_length = st.number_input("Maximum summary length (words):", min_value=min_length, max_value=1000, value=100, key='sbt_max_length')

    if st.button("Summarize", key='sbt_summarize'):
        summary = summarize(st.session_state.text, min_length=min_length, max_length=max_length)
        if summary:
            st.session_state.summary = summary
            print("Summary evaluation (in terminal):")
            metrics = evaluate_summary(st.session_state.text, summary)
            print(f"ROUGE-1: {metrics['ROUGE-1']:.4f}")
            print(f"ROUGE-2: {metrics['ROUGE-2']:.4f}")
            print(f"ROUGE-L: {metrics['ROUGE-L']:.4f}")
            print(f"BLEU: {metrics['BLEU']:.4f}")
            print(f"BERTScore (F1): {metrics['BERTScore (F1)']:.4f}")
            st.session_state.stage = 'translation_after_summarization'

# Stage: Translation after Summarization
if st.session_state.stage == 'translation_after_summarization':
    st.subheader("Translation Settings")
    output_language = st.text_input("Enter the target language code (e.g., 'fa' for Persian):", value="fa", key='tas_output_language')
    model_option = st.selectbox("Select the translation model:", 
                                ["SeamlessM4T", "Opus-MT", "MADLAD400"], key='tas_model_option')
    model_index = ["SeamlessM4T", "Opus-MT", "MADLAD400"].index(model_option)

    if st.button("Translate", key='tas_translate'):
        translated_text = translate_text(st.session_state.summary, output_language, model_index)
        if translated_text:
            st.write("**Translated Summary:**")
            st.write(translated_text)
            st.session_state.stage = 'done'

# Stage: Translation before Summarization
if st.session_state.stage == 'translation_before_summarization':
    st.subheader("Translation Settings")
    output_language = st.text_input("Enter the target language code (e.g., 'fa' for Persian):", value="fa", key='tbs_output_language')
    model_option = st.selectbox("Select the translation model:", 
                                ["SeamlessM4T", "Opus-MT", "MADLAD400"], key='tbs_model_option')
    model_index = ["SeamlessM4T", "Opus-MT", "MADLAD400"].index(model_option)

    if st.button("Translate", key='tbs_translate'):
        translated_text = translate_text(st.session_state.text, output_language, model_index)
        if translated_text:
            st.session_state.translated_text = translated_text
            st.session_state.stage = 'summarization_after_translation'

# Stage: Summarization after Translation
if st.session_state.stage == 'summarization_after_translation':
    st.subheader("Summarization Settings")
    min_length = st.number_input("Minimum summary length (words):", min_value=5, max_value=500, value=50, key='sat_min_length')
    max_length = st.number_input("Maximum summary length (words):", min_value=min_length, max_value=1000, value=100, key='sat_max_length')

    if st.button("Summarize", key='sat_summarize'):
        summary = summarize(st.session_state.translated_text, min_length=min_length, max_length=max_length)
        if summary:
            st.write("**Summarized Translation:**")
            st.write(summary)
            print("Summary evaluation (in terminal):")
            metrics = evaluate_summary(st.session_state.text, summary)
            print(f"ROUGE-1: {metrics['ROUGE-1']:.4f}")
            print(f"ROUGE-2: {metrics['ROUGE-2']:.4f}")
            print(f"ROUGE-L: {metrics['ROUGE-L']:.4f}")
            print(f"BLEU: {metrics['BLEU']:.4f}")
            print(f"BERTScore (F1): {metrics['BERTScore (F1)']:.4f}")
            st.session_state.stage = 'done'

# Final stage: Done
if st.session_state.stage == 'done':
    if st.button("Start Over"):
        st.session_state.clear()
