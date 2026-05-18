# Greek Medical Report Anonymization

This tool anonymizes Greek medical reports through a simple local web interface.

It supports:

- one report at a time
- multiple reports uploaded together
- a `.zip` archive containing a folder of reports

## Download The Tool

1. Open the repository page in your browser.
2. Click `Code`.
3. Click `Download ZIP`.
4. Extract the downloaded ZIP file.
5. Open the extracted folder.

## First-Time Setup

This step is needed only once.

Open `Terminal` and go to the extracted folder.

Then run:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[ml,ui]'
```

The model files should be placed in:

```text
models/xlmr_phi_final
```

## Start The App

After the first-time setup:

- on Mac, double-click `Start_Anonymizer.command`
- on Windows, double-click `Start_Anonymizer.bat`

If the browser does not open automatically, open:

```text
http://localhost:8501
```

## How To Use

1. Select the report type.
2. Upload one report, multiple reports, or a `.zip` file containing a folder of reports.
3. If needed, change the mask token under `Advanced options`.
4. Click `Run anonymization`.
5. Download the generated `.zip` file.

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
- For folder upload, first create a real `.zip` archive of the folder.
- The tool runs locally on the computer where it is launched.
