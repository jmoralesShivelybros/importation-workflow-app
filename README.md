# Importation Workflow Application

This project automates parts of the importation workflow, specifically for organizing weekly folders, extracting data from PDFs, managing invoices, and generating emails for export requests.

## Project Structure

```
importation-workflow-app
├── src
│   ├── main.py
│   ├── folder_manager.py
│   ├── pdf_extractor.py
│   ├── invoice_manager.py
│   ├── email_generator.py
│   └── types
│       └── __init__.py
├── requirements.txt
└── README.md
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd importation-workflow-app
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the application, execute the following command:
```
python src/main.py
```

## Functionality

- **Folder Management**: Automatically creates and organizes weekly folders.
- **PDF Data Extraction**: Extracts relevant data from PDF files, including order references and shipping details.
- **Invoice Management**: Requests invoices via email and logs them in an Excel file.
- **Email Generation**: Generates and sends emails for export requests to specified recipients.

## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.