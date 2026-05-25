# Greek Medical Report Anonymization

This tool anonymizes Greek medical reports through a simple Google Colab notebook.

## Open In Colab

Open the notebook here:

[Open in Colab](https://colab.research.google.com/github/VanessaLislevand/greek-medical-anonymization/blob/main/Launch_App.ipynb)

## How To Start

1. Open the notebook in Colab.
2. Run the cells from top to bottom.
3. Upload one report, multiple reports, or a `.zip` file containing a folder of reports.
4. Review the preview shown inside Colab.
5. Download the generated `.zip` file.

The notebook will:

- download the repository
- install the required packages
- mount Google Drive
- connect the pipeline to the model files stored in Google Drive
- anonymize the uploaded reports
- show a preview of the anonymized output inside the notebook
- download the output `.zip`

## Notebook Settings

Inside the notebook you can change:

- `PROCESSING_MODE`
- `MASK_TOKEN`
- `DEFAULT_MODEL_DIR`

## Report Types

- `Report with template and free text`: for reports that contain both structured fields and free text
- `Free-text-only report`: for narrative reports without a fixed template
- `Template-only report`: for reports that are mostly structured template fields

## Output

The downloaded `.zip` file contains:

- one anonymized text file for each report
- one `.json` metadata file for each report

## Notes

- Input reports can be `.docx` or `.txt`.
- Folder upload should be provided as a real `.zip` archive.
- The model files should be stored in Google Drive.
- The notebook first tries the default model path in Google Drive and asks for another path only if needed.
