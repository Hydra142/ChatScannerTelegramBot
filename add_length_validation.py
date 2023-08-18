import re

# Open the source file
with open('text.txt', 'r', encoding='utf-8') as source_file:
    source_text = source_file.read()

# Define the regex pattern
regex_pattern = r"entity\.Property\(e => e\.(\w+)\)\s*\.HasMaxLength\((\d+)\)"

# Search the source text for matches
matches = re.findall(regex_pattern, source_text)

# Open the result file
with open('result.txt', 'w') as result_file:

    # Iterate over the matches
    for match in matches:
        field_name = match[0]
        max_length = match[1]

        # Write the desired code to the result file
        result_file.write(f"""if ({field_name} != null && {field_name}.Length > {max_length})
{{
    validationResult.ValidationErrorMessages.Add($"Field {field_name} is too long({{{field_name}.Length}}), max len is {max_length}");
}}
""")

print("The result.txt file has been written successfully.")