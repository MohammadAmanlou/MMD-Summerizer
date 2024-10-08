# -*- coding: utf-8 -*-
"""Translate.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1FDINYMt84uuz_jH-8CZ1fDo9t8Ok85IZ
"""

from transformers import MarianMTModel, MarianTokenizer

def translate_text(input_file, output_file, model_name="Helsinki-NLP/opus-mt-en-roa"):
    # Load the model and tokenizer
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)

    # Read the input text from the file
    with open(input_file, "r", encoding="utf-8") as file:
        text = file.read()

    # Tokenize the input text
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)

    # Generate translation using the model
    translated = model.generate(**inputs)

    # Decode the translated tokens into text
    translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)

    # Write the translated text to the output file
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(translated_text)

    print(f"Translation completed. Translated text saved to {output_file}")

# Specify the input and output files
input_file = "input_text.txt"
output_file = "translated_text.txt"

# Call the translate_text function
translate_text(input_file, output_file)