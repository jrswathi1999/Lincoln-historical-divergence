"""
Configuration for Event Extraction

Defines the 5 key events we need to extract information about.
"""

# The 5 key events from the assessment
KEY_EVENTS = [
    {
        "id": "election_night_1860",
        "name": "Election Night 1860",
        "keywords": ["election night 1860", "November 1860", "1860 election", "election results", "presidential election", "election", "1860", "November"]
    },
    {
        "id": "fort_sumter",
        "name": "Fort Sumter Decision",
        "keywords": ["Fort Sumter", "Sumter", "Charleston", "April 1861", "resupply", "firing", "bombardment", "surrender"]
    },
    {
        "id": "gettysburg_address",
        "name": "Gettysburg Address",
        "keywords": ["Gettysburg Address", "Gettysburg", "November 1863", "dedication", "cemetery", "four score", "battlefield"]
    },
    {
        "id": "second_inaugural",
        "name": "Second Inaugural Address",
        "keywords": ["Second Inaugural", "March 1865", "inauguration", "second term", "inaugural address", "1865"]
    },
    {
        "id": "fords_theatre",
        "name": "Ford's Theatre Assassination",
        "keywords": ["Ford's Theatre", "assassination", "April 14 1865", "John Wilkes Booth", "shot", "theater", "theatre", "Booth", "killed", "murdered"]
    }
]

# Expected output schema for event extraction
EXTRACTION_SCHEMA = {
    "event": "string (event ID)",
    "author": "string (book/document author)",
    "claims": ["list of claim strings"],
    "temporal_details": {
        "date": "string (if mentioned)",
        "time": "string (if mentioned)"
    },
    "tone": "string (e.g., Sympathetic, Critical, Neutral)"
}

