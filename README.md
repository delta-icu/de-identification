# Greek Medical Report Anonymization

This tool anonymizes Greek medical reports through a simple Google Colab notebook.

## Open In Colab

Open the notebook here:

[Open in Colab](https://colab.research.google.com/github/VanessaLislevand/greek-medical-anonymization/blob/main/Run_Anonymization_Colab.ipynb)

## How To Start

1. Open the notebook in Colab.
2. Run the cells from top to bottom.
3. Upload one report, multiple reports, or a `.zip` file containing a folder of reports.
4. Review the full anonymized report shown inside Colab.
5. Click the download button to save the generated `.zip` file.

The notebook will:

- download the repository
- install the required packages
- download the model from a shareable link
- connect the pipeline to the downloaded model files
- anonymize the uploaded reports
- show the full anonymized output inside the notebook
- provide a download button for the output `.zip`

## Notebook Settings

Inside the notebook you can change:

- `REPORT_TYPE`
- `MASK_TOKEN`

## Report Types

- `Report with template and free text`: for reports that contain both structured fields and free text
- `Free-text-only report`: for narrative reports without a fixed template

## Output

The downloaded `.zip` file contains:

- one anonymized text file for each report
- one `.json` metadata file for each report

## Notes

- Input reports can be `.docx` or `.txt`.
- Folder upload should be provided as a real `.zip` archive.
- The notebook downloads the model from a shareable link defined in the model-loading cell.
