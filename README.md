# Deepin Autopack

Deepin Autopack is an automated packaging management system designed to streamline the process of building and deploying projects. This project integrates with Git, Gerrit, GitHub, and CRP platforms to facilitate continuous integration and deployment.

## Features

- **Project Configuration**: Easily configure project settings including repository URLs and branches.
- **Commit Monitoring**: Monitor commits from Gerrit and automatically sync with GitHub.
- **Automated Packaging**: Automatically build and package projects based on the latest commits.
- **User-Friendly Interface**: A simple and elegant web interface built with Flask.

## Project Structure

```
deepin-autopack
├── app
│   ├── __init__.py          # Initializes the Flask application
│   ├── models                # Contains data models
│   │   ├── __init__.py
│   │   ├── project.py        # Project-related models
│   │   ├── config.py         # Configuration models
│   │   └── build_log.py      # Build log models
│   ├── routes                # Contains route definitions
│   │   ├── __init__.py
│   │   ├── project.py        # Routes for project management
│   │   ├── config.py         # Routes for configuration management
│   │   ├── monitor.py        # Routes for monitoring commits
│   │   └── build.py          # Routes for building projects
│   ├── services              # Contains service logic
│   │   ├── __init__.py
│   │   ├── git_service.py     # Git operations
│   │   ├── gerrit_service.py  # Gerrit operations
│   │   ├── github_service.py   # GitHub operations
│   │   └── crp_service.py      # CRP operations
│   ├── templates             # HTML templates
│   │   ├── base.html         # Base template
│   │   ├── index.html        # Home page template
│   │   ├── project_list.html  # Project list template
│   │   ├── project_form.html   # Project form template
│   │   ├── config.html       # Configuration template
│   │   ├── monitor.html      # Monitoring template
│   │   └── build.html        # Build status template
│   └── static                # Static files (CSS, JS)
│       ├── css
│       │   └── style.css     # Stylesheet
│       └── js
│           └── main.js       # JavaScript logic
├── config.py                 # Global configuration
├── requirements.txt          # Python dependencies
├── run.py                    # Entry point to run the application
└── README.md                 # Project documentation
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd deepin-autopack
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Configure the application by editing `config.py`.

4. Run the application:
   ```
   python run.py
   ```

## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any suggestions or improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.