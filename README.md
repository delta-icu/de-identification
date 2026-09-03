# Greek Medical Report Anonymization

This repository provides two ways to anonymize Greek medical reports:

1. a local web app
2. a Google Colab notebook

The main way to use this repository is the local web app.

## Web App

The web app:

- accepts `.docx`, `.doc`, `.txt`, or `.zip` files
- supports one or multiple reports
- shows the full anonymized output on screen
- lets you download a `.zip` file with the results
- downloads the model automatically the first time it runs

You need:

- Python 3.10 or newer
- internet access the first time the app runs

### About `.doc` files

Older `.doc` files are converted automatically before anonymization.

One thing to know: on a Mac without LibreOffice, the conversion can leave out
headers and footers. If your reports keep the hospital name or the doctor's name
up there, either install [LibreOffice](https://www.libreoffice.org/download/) or
save the file as `.docx` in Word first, so nothing is missed.

Typical times:

- first setup: about 5-15 minutes
- opening the app after setup: usually a few seconds
- first anonymization run: usually slower, because the model may need to be downloaded and loaded
- next app launches: faster than the first time

## Windows Setup

### First Time Only

1. Download this repository from GitHub as a `.zip` file and extract it.
2. Open the extracted folder.
3. Double-click `Launch_Web_App_Windows.bat`.
4. Wait while the app prepares the environment. The first run may take several minutes.

The launcher will:

- find or set up a suitable Python
- install the required packages the first time
- open the web app

The app should open at:

`http://localhost:8501`

### Next Times

Double-click `Launch_Web_App_Windows.bat` again.

## Mac Setup

### First Time Only

1. Download this repository from GitHub as a `.zip` file and extract it.
2. Open the extracted folder.
3. Double-click `Launch_Web_App_Mac.command`.
4. macOS will block it the first time. See below.
5. Wait while the app prepares the environment. The first run may take several minutes.

The launcher will:

- find or set up a suitable Python
- install the required packages the first time
- open the web app

The app should open at:

`http://localhost:8501`

### If macOS Blocks The Launcher

The first time, macOS says it "could not verify" the file. This is expected: it
is a script downloaded from the internet, and it has not been signed with an
Apple developer certificate. To allow it:

1. Double-click `Launch_Web_App_Mac.command` and dismiss the warning.
2. Open System Settings, then Privacy & Security.
3. Scroll down to Security. Next to "Launch_Web_App_Mac.command was blocked",
   click Open Anyway.
4. Confirm, and enter your password or use Touch ID.

You only need to do this once.

Two ways to avoid it altogether:

- Get the project with `git clone` instead of downloading the `.zip`. Files from
  a clone are not marked as downloaded, so macOS does not block them.
- Or run this once in Terminal, from inside the project folder:

  ```bash
  xattr -d com.apple.quarantine Launch_Web_App_Mac.command
  ```

### Next Times

Double-click `Launch_Web_App_Mac.command` again.

## How To Use The Web App

1. Choose the report type.
2. Keep the default mask token or change it.
3. Upload one or more `.docx`, `.doc`, or `.txt` files.
4. If you want to upload a whole folder, first compress it as a real `.zip` file and upload the `.zip`.
5. Click `Run anonymization`.
6. Review the anonymized output shown on screen.
7. Download the generated `.zip` file.

Note:

- you do not need to reinstall the package every time
- you usually install only once per computer and per project folder

## Report Types

- `Report with template and free text`: for reports with structured template fields and narrative text
- `Free-text-only report`: for reports that only contain narrative text

## Output

The downloaded `.zip` file contains:

- one anonymized text file for each report
- one `.json` metadata file for each report

## Notebook

The notebook is available as an alternative option:

[Open in Colab](https://colab.research.google.com/github/VanessaLislevand/greek-medical-anonymization/blob/main/Run_Anonymization_Colab.ipynb)

Inside Colab:

1. open the notebook
2. run the cells from top to bottom
3. upload your files
4. review the anonymized output
5. download the generated `.zip`
