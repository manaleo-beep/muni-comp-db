"""
Generates a realistic sample compensation dataset for VT/NH/ME municipalities.
Run once: python generate_sample_data.py
Produces: sample_data.csv  (ready to upload via the app's Upload tab)
"""
import pandas as pd
import random

random.seed(42)  # reproducible

# Real municipalities with 2020 census populations
MUNIS = [
    # Vermont
    ("Burlington","VT","Chittenden",44743,"Mayor-Council"),
    ("South Burlington","VT","Chittenden",20292,"Council-Manager"),
    ("Rutland","VT","Rutland",15807,"Mayor-Aldermen"),
    ("Essex","VT","Chittenden",22094,"Selectboard-Manager"),
    ("Colchester","VT","Chittenden",17524,"Selectboard-Manager"),
    ("Barre City","VT","Washington",8491,"Mayor-Council"),
    ("Montpelier","VT","Washington",8074,"Council-Manager"),
    ("Brattleboro","VT","Windham",12184,"Selectboard-Manager"),
    ("Bennington","VT","Bennington",15333,"Selectboard-Manager"),
    ("Hartford","VT","Windsor",10686,"Selectboard-Manager"),
    ("Middlebury","VT","Addison",9152,"Selectboard-Manager"),
    ("St. Albans City","VT","Franklin",6877,"Mayor-Manager"),
    ("Williston","VT","Chittenden",10103,"Selectboard-Manager"),
    ("Stowe","VT","Lamoille",5164,"Selectboard-Manager"),
    ("Shelburne","VT","Chittenden",7717,"Selectboard-Manager"),
    # New Hampshire
    ("Manchester","NH","Hillsborough",115644,"Mayor-Aldermen"),
    ("Nashua","NH","Hillsborough",91322,"Mayor-Aldermen"),
    ("Concord","NH","Merrimack",43976,"Council-Manager"),
    ("Derry","NH","Rockingham",34317,"Council-Administrator"),
    ("Dover","NH","Strafford",32741,"Council-Manager"),
    ("Rochester","NH","Strafford",32492,"Mayor-Council"),
    ("Salem","NH","Rockingham",30089,"Selectmen-Manager"),
    ("Merrimack","NH","Hillsborough",26632,"Council-Manager"),
    ("Hudson","NH","Hillsborough",25394,"Selectmen-Administrator"),
    ("Londonderry","NH","Rockingham",25826,"Council-Manager"),
    ("Keene","NH","Cheshire",23047,"Council-Manager"),
    ("Bedford","NH","Hillsborough",23322,"Council-Manager"),
    ("Portsmouth","NH","Rockingham",21956,"Council-Manager"),
    ("Goffstown","NH","Hillsborough",18577,"Selectmen-Administrator"),
    ("Laconia","NH","Belknap",16871,"Mayor-Manager"),
    ("Hanover","NH","Grafton",11870,"Selectmen-Manager"),
    ("Lebanon","NH","Grafton",14282,"Council-Manager"),
    ("Exeter","NH","Rockingham",16049,"Selectmen-Manager"),
    # Maine
    ("Portland","ME","Cumberland",68408,"Council-Manager"),
    ("Lewiston","ME","Androscoggin",37121,"Mayor-Administrator"),
    ("Bangor","ME","Penobscot",31753,"Council-Manager"),
    ("South Portland","ME","Cumberland",26498,"Council-Manager"),
    ("Auburn","ME","Androscoggin",24061,"Mayor-Council"),
    ("Biddeford","ME","York",22552,"Mayor-Council"),
    ("Sanford","ME","York",21982,"Council-Manager"),
    ("Brunswick","ME","Cumberland",21756,"Council-Manager"),
    ("Saco","ME","York",20381,"Mayor-Administrator"),
    ("Westbrook","ME","Cumberland",20400,"Mayor-Administrator"),
    ("Augusta","ME","Kennebec",18899,"Council-Manager"),
    ("Waterville","ME","Kennebec",15828,"Mayor-Manager"),
    ("Scarborough","ME","Cumberland",22135,"Council-Manager"),
    ("Gorham","ME","Cumberland",18400,"Council-Manager"),
    ("Falmouth","ME","Cumberland",12444,"Council-Manager"),
    ("Kennebunk","ME","York",11536,"Selectmen-Manager"),
    ("Camden","ME","Knox",5232,"Selectmen-Manager"),
]

# Standard positions with base salary (national midpoint ~25K pop)
POSITIONS = {
    "Town Manager":        130000,
    "Finance Director":     95000,
    "Police Chief":        115000,
    "Fire Chief":          110000,
    "DPW Director":         95000,
    "Town Clerk":           65000,
    "Planner":              75000,
    "Library Director":     72000,
    "Recreation Director":  68000,
    "Assessor":             78000,
}

# Some towns use alias titles — exercises the mapping engine
ALIASES = {
    "Town Manager":   ["City Manager","Town Administrator","City Administrator"],
    "DPW Director":   ["Public Works Director","Highway Superintendent"],
    "Town Clerk":     ["City Clerk","Town Clerk/Treasurer"],
    "Finance Director":["Director of Finance","Business Manager"],
}

def pop_multiplier(pop):
    if pop > 60000: return 1.55
    if pop > 35000: return 1.35
    if pop > 22000: return 1.20
    if pop > 15000: return 1.05
    if pop >  9000: return 0.92
    return 0.80

def state_adj(state):
    return {"VT":1.00,"NH":1.04,"ME":0.97}[state]

rows = []
for muni,state,county,pop,gov in MUNIS:
    mult = pop_multiplier(pop) * state_adj(state)
    for std_title, base in POSITIONS.items():
        # Skip some positions for very small towns (realistic)
        if pop < 8000 and std_title in ("Planner","Recreation Director"):
            if random.random() < 0.6: continue
        # Use an alias title 30% of the time
        title = std_title
        if std_title in ALIASES and random.random() < 0.3:
            title = random.choice(ALIASES[std_title])
        # Small/large city logic for top exec
        if std_title == "Town Manager" and pop > 30000:
            title = random.choice(["City Manager","City Administrator"])
        salary = base * mult * random.uniform(0.92, 1.08)
        salary = round(salary / 500) * 500  # round to nearest $500
        min_sal = round(salary * 0.85 / 500)*500
        max_sal = round(salary * 1.15 / 500)*500
        benefits_pct = round(random.uniform(28, 35), 1)
        total_comp = round(salary * (1 + benefits_pct/100))
        rows.append({
            "municipality": muni,
            "state": state,
            "county": county,
            "fiscal_year": 2024,
            "population": pop,
            "form_of_government": gov,
            "position_title": title,
            "actual_salary": salary,
            "min_salary": min_sal,
            "max_salary": max_sal,
            "hours_per_week": 40,
            "benefits_pct": benefits_pct,
            "total_comp": total_comp,
        })

df = pd.DataFrame(rows)
df.to_csv("sample_data.csv", index=False)
print(f"✅ Generated sample_data.csv with {len(df)} rows across {len(MUNIS)} municipalities.")
print(df.head(10))