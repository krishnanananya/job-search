# Copy this file to profile.py and fill in your details:
#   cp config/profile.example.py config/profile.py

PROFILE = {
    "name": "Your Name",
    "education": [
        {"school": "University Name", "degree": "M.S. Example", "gpa": 3.8, "year": 2025},
    ],
    "years_experience": 3,
    "skills": [
        "python", "sql", "statistics", "machine learning",
        # add skills that should boost job match scores
    ],
    "target_locations": {
        "sf_bay_area": [
            "san francisco", "sf", "bay area", "palo alto", "mountain view",
            "menlo park", "redwood city", "san mateo", "sunnyvale",
            "santa clara", "san jose", "oakland", "berkeley",
        ],
        "nyc": [
            "new york", "nyc", "manhattan", "brooklyn", "jersey city",
            "new york city", "new york, ny",
        ],
    },
    "min_salary": 120_000,
}
