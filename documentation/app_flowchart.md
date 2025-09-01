flowchart TD
    LP[Landing Page] --> FTU{First Time User?}
    FTU -->|Yes| SU[Sign Up]
    FTU -->|No| SI[Sign In]
    SU --> EA[Email Activation]
    EA --> SI
    SI --> Dashboard[Main Dashboard]
    Dashboard --> Docs[Documentation]
    Dashboard --> Explorer[API Explorer]
    Dashboard --> Examples[Examples]
    Dashboard --> Settings[Account Settings]
    Docs --> Dashboard
    Explorer --> Dashboard
    Examples --> Dashboard
    Settings --> Dashboard
    Explorer --> CheckPOST[Send POST v1 check]
    CheckPOST --> Explorer
    Explorer --> CheckGET[Send GET v1 status]
    CheckGET --> Explorer
    Settings --> RegToken[Regenerate Token]
    RegToken --> Settings
    SU --> Error[Error Handling]
    SI --> Error
    Explorer --> Error
    Error --> Dashboard
    Dashboard --> Offline[Offline Banner]
    Offline --> Dashboard