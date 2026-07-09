"""Text content for the ResearchSense FYP report (Chapters 1 to 4).

All prose is written in plain English and is original to this project. Dashes
are avoided on purpose. Placeholders in square brackets are for the student to
fill before submission.
"""

TITLE = "ResearchSense: A Research Information System for Bahria University Islamabad, E-8 Campus"
AUTHOR = "Ammar Jamil"
ENROLLMENT = "[Enrollment Number]"
SUPERVISOR = "[Supervisor Name]"
CO_SUPERVISOR = "[Co-Supervisor Name]"
DEGREE = "Bachelor of Science in Computer Science"
DEPARTMENT = "Department of Computer Science"
UNIVERSITY = "Bahria University, Islamabad"
DATE = "2026"

ABSTRACT = [
    "ResearchSense is a web based research information system built for Bahria "
    "University Islamabad, E-8 campus. Universities produce a large amount of "
    "research every year, but the records of researchers, publications, and "
    "projects are often spread across separate files and web pages. This makes "
    "it hard for students, faculty, and outside visitors to find who works on a "
    "topic or what work the campus has produced.",

    "ResearchSense brings this information into one clear place. It offers "
    "researcher profiles, a searchable list of publications, a set of research "
    "areas, funded projects, a tool that suggests possible collaborators, and a "
    "simple assistant that answers questions in plain language. The system uses "
    "a React and TypeScript interface with a FastAPI service behind it.",

    "The design keeps the data layer separate from the rest of the system. "
    "Because of this, the current sample data can later be replaced by a real "
    "database without changing the pages or the business logic. This report "
    "presents the background, the review of similar systems, the requirements, "
    "and the design of the first version of the product.",
]

# ---------------------------------------------------------------------------
# Chapter 1: Introduction
# ---------------------------------------------------------------------------
CH1 = {
    "title": "Introduction",
    "sections": [
        ("Project Background and Overview", [
            "Research is one of the main tasks of any university. Faculty members "
            "write papers, lead funded projects, and guide students in new areas "
            "of study. Over time this work becomes a large record of knowledge "
            "that belongs to the whole institution. A good university keeps this "
            "record visible so that people inside and outside the campus can see "
            "what is being studied and by whom.",

            "At present the research record of Bahria University Islamabad, E-8 "
            "campus is hard to view as a whole. Faculty details sit on one set of "
            "pages, while publication lists, if they exist, sit somewhere else or "
            "on personal profiles on outside websites. A visitor who wants to know "
            "which teachers work on machine learning, or how many papers the "
            "campus has produced in a field, has no single place to look.",

            "ResearchSense is a research information system that solves this "
            "problem. It collects the profiles of researchers, their publications, "
            "the topics they study, and the projects they lead, and it presents "
            "all of this through one clean web portal. The idea follows the style "
            "of well known university research portals, but it is shaped for the "
            "needs of Bahria University and uses the real faculty of the E-8 "
            "campus as its starting data.",
        ]),
        ("Problem Description", [
            "The main problem is that research information at the campus is "
            "scattered and hard to search. This creates several smaller problems.",

            "First, students and new researchers cannot easily find a supervisor "
            "or a partner who shares their interests. They have to ask people by "
            "hand or read many separate pages. Second, the campus cannot show its "
            "research strength in a clear way, because there is no single view of "
            "how many researchers, papers, and projects it has. Third, useful "
            "links between people who study the same topic stay hidden, so chances "
            "for teamwork are missed. Fourth, there is no simple way to ask a "
            "plain question, such as who works on cybersecurity, and get a direct "
            "answer.",

            "ResearchSense is built to remove these gaps by placing all the "
            "information in one searchable and connected system.",
        ]),
        ("Project Objectives", [
            "The objectives of the project are listed below.",
        ], [
            "Build one web portal that shows researcher profiles, publications, "
            "research areas, and projects for the campus.",
            "Make the information easy to search and filter by name, department, "
            "designation, topic, and year.",
            "Show the research strength of the campus through clear counts and "
            "featured profiles on the home page.",
            "Suggest possible collaborators by linking researchers who share the "
            "same research topics.",
            "Provide a simple assistant that answers plain language questions and "
            "points the user to the right people and areas.",
            "Keep the data layer separate so that a real database can be added "
            "later without a rewrite of the system.",
        ]),
        ("Project Scope", [
            "This first version of ResearchSense focuses on the full user "
            "interface and a working service that supplies data to it. The data "
            "for this version comes from the real faculty list of the Computer "
            "Science department at the E-8 campus, including real emails, research "
            "areas, and qualifications, together with real publications collected "
            "from the OpenAlex scholarly database. Project and funding records are "
            "sample values that are clearly marked as sample. The system runs as a "
            "web application that any modern browser can open.",

            "The following items are planned for later phases and are not part of "
            "this version: user login and accounts, a live database, automatic "
            "reading of papers to find topics, and a full question answering "
            "engine that reads document text. The current design leaves a clean "
            "place for each of these to be added without changing the parts that "
            "are already built.",
        ]),
    ],
}

# ---------------------------------------------------------------------------
# Chapter 2: Literature Review
# ---------------------------------------------------------------------------
CH2 = {
    "title": "Literature Review",
    "sections": [
        ("Overview", [
            "A literature review looks at systems that solve a similar problem, "
            "studies what they do well, and finds the gaps that a new project can "
            "fill. Research information systems are not a new idea. Many "
            "universities and companies already run tools that store and show "
            "research output. This chapter reviews the most common ones and then "
            "explains where ResearchSense fits.",
        ]),
        ("Existing Research Portals and Tools", [
            "Elsevier Pure is a widely used research information system. It gathers "
            "profiles, publications, and activities for a university and shows "
            "them through a public portal. It is powerful but it is a paid "
            "product, and it is built for large institutions that already have "
            "clean data feeds. Small departments often cannot afford it or set it "
            "up quickly.",

            "VIVO is an open source system that stores research information as "
            "linked data. It is flexible and free, but it needs technical effort "
            "to install and to keep running, and its default look is plain. "
            "DSpace is another open tool, but it is mainly a repository for files "
            "and documents rather than a rich profile and discovery portal.",

            "ORCID and Google Scholar solve a related but different problem. They "
            "give each researcher a personal profile and a list of papers. They "
            "are useful, but they are centred on the individual, not on the "
            "campus as a whole. A visitor cannot use them to see the combined "
            "research strength of one department or to browse local topics and "
            "projects in one place.",

            "Some universities build their own portals. A clear example is the "
            "research portal of Nazarbayev University, which presents profiles, "
            "research output, and topic areas through a clean public site. It "
            "shows that a focused portal can make an institution's research easy "
            "to explore. ResearchSense takes this style of portal as a reference "
            "for its layout and features.",
        ]),
        ("Gaps and the Need for ResearchSense", [
            "From this review three points stand out. The paid systems are strong "
            "but costly and heavy for a single campus. The free systems are open "
            "but need real effort to run and often look plain. The personal "
            "profile services are helpful but do not give a campus wide view.",

            "There is also a common gap in local discovery. Few of these tools, "
            "in their basic form, suggest who a researcher could work with, or let "
            "a user ask a plain question and get a direct answer. For a single "
            "department that wants a clear, attractive, and low cost portal, none "
            "of the existing options fits well on its own.",

            "ResearchSense aims to fill this gap. It offers a clean and modern "
            "portal shaped for one campus, it links researchers by shared topics "
            "to support teamwork, and it includes a simple assistant for plain "
            "questions. It is built with a clear separation between the interface, "
            "the logic, and the data, so it stays easy to maintain and to extend.",
        ]),
    ],
}

# ---------------------------------------------------------------------------
# Chapter 3: Requirement Specifications
# ---------------------------------------------------------------------------
CH3 = {
    "title": "Requirement Specifications",
    "sections": [
        ("Existing System", [
            "The existing way of sharing research information at the campus is "
            "made of separate parts. Faculty names and titles appear on "
            "department web pages. Publication lists, when they are public, live "
            "on personal pages or on outside services. Project and funding details "
            "are usually kept in office files and are not shown online.",

            "This existing setup has clear drawbacks. The information is spread "
            "out, so a full view is missing. Search is weak or absent, so finding "
            "a person by topic is slow. Links between researchers who share "
            "interests are not shown at all. Because the parts are not connected, "
            "the campus cannot present its research as one clear story.",
        ]),
        ("Proposed System", [
            "The proposed system, ResearchSense, replaces the scattered setup with "
            "one connected portal. It stores researchers, publications, topics, "
            "and projects in a single model and shows them through linked pages. "
            "A visitor can start from the home page, move to a researcher profile, "
            "see that person's papers and topics, and then jump to a suggested "
            "collaborator, all without leaving the portal.",

            "The proposed system adds features that the existing setup does not "
            "have. It counts the research output of the campus and shows it on the "
            "home page. It lets users filter people and papers in many ways. It "
            "suggests collaborators based on shared topics. It also offers a "
            "simple assistant that turns a plain question into a helpful answer "
            "with links.",
        ]),
        ("Functional Requirements", [
            "The functional requirements describe what the system must do.",
        ], [
            "The system shall show a home page with search, live counts, featured "
            "researchers, and a list of research areas.",
            "The system shall list all researchers and allow filtering by "
            "department, designation, and topic, and searching by name.",
            "The system shall show a full profile for each researcher, including "
            "biography, research areas, publications, and suggested collaborators.",
            "The system shall list publications and allow filtering by year and "
            "topic and searching by title.",
            "The system shall list research areas and show how many publications "
            "and researchers belong to each area.",
            "The system shall list funded projects with their status, dates, lead "
            "researcher, and funding details.",
            "The system shall show a collaboration view that links a chosen "
            "researcher to others who share topics.",
            "The system shall provide an assistant that accepts a plain question "
            "and returns an answer with links to relevant people and areas.",
        ]),
        ("Non Functional Requirements", [
            "The non functional requirements describe the quality goals of the "
            "system.",
        ], [
            "Usability: the portal shall be clear and easy to use on both desktop "
            "and mobile screens.",
            "Performance: pages shall load quickly, and repeated data shall be "
            "cached on the client to avoid extra requests.",
            "Maintainability: the code shall be split into small focused files, "
            "with the interface, the logic, and the data kept separate.",
            "Portability: the system shall run through any modern web browser "
            "without special software on the user side.",
            "Extensibility: the data layer shall sit behind a clear boundary so a "
            "real database can be added later with little change elsewhere.",
            "Reliability: when the service cannot be reached, the interface shall "
            "show a clear message instead of failing without notice.",
        ]),
        ("Use Cases", [
            "The main users of the system are the visitor, who can be a student, a "
            "faculty member, or an outside guest, and the future administrator, "
            "who will manage records once accounts are added. The key use cases "
            "for the current version are listed below.",
        ], [
            "Search for a researcher by name or by research area.",
            "Browse the researcher directory and apply filters.",
            "View a researcher profile and open a suggested collaborator.",
            "Browse and filter publications by year and topic.",
            "Explore research areas and open the work under an area.",
            "View funded projects and their funding details.",
            "Ask the assistant a plain question and follow its links.",
        ]),
    ],
}

# ---------------------------------------------------------------------------
# Chapter 4: Design
# ---------------------------------------------------------------------------
CH4 = {
    "title": "Design",
    "sections": [
        ("System Architecture", [
            "ResearchSense follows a client and server design. The client is a "
            "single page web application built with React and TypeScript. The "
            "server is an application programming interface built with FastAPI in "
            "Python. The client asks the server for data over simple web requests "
            "and shows the results. The client never reads the data source "
            "directly; it only speaks to the server through a small set of typed "
            "functions.",

            "On the server the work flows through four clear layers. A router "
            "receives each request. A service holds the business logic. A "
            "repository reads and writes the data. A data source holds the actual "
            "records. In this version the data source is a set of JSON files that "
            "hold the real faculty and the sample research records. Because the "
            "repository hides the data source behind a fixed boundary, the JSON "
            "source can later be swapped for a real database while the router and "
            "the service stay the same.",
        ]),
        ("Design Constraints", [
            "The design works within a few constraints. Publications are real and "
            "come from the OpenAlex scholarly database, matched to Bahria "
            "affiliated authors. Project and funding records are sample data, "
            "since the campus does not publish these in a single feed, and they "
            "are marked as sample so their origin is always clear. The system does "
            "not include login or a live database in this phase, which keeps the "
            "current scope focused on the interface and the service.",

            "A further constraint is set by the team itself. Every source file is "
            "kept small, with one clear purpose, so the code stays easy to read "
            "and to change. This rule shapes how the pages and the server modules "
            "are divided.",
        ]),
        ("Design Methodology", [
            "The project uses an object based and component based method. On the "
            "server, each resource, such as a researcher or a publication, has its "
            "own schema, service, and repository. On the client, the interface is "
            "built from small reusable components that are grouped into feature "
            "folders and page folders.",

            "The guiding ideas are separation of concerns, loose coupling, and "
            "high cohesion. Separation of concerns means each part has one job. "
            "Loose coupling means parts depend on each other as little as "
            "possible. High cohesion means the pieces inside one part belong "
            "together. These ideas make the system easier to test and to grow.",
        ]),
        ("High Level Design", [
            "At a high level the system has three groups of parts. The first group "
            "is the client interface, which holds the pages, the shared "
            "components, and the typed functions that call the server. The second "
            "group is the server logic, which holds the routers and the services. "
            "The third group is the data access, which holds the repositories and "
            "the data source.",

            "A request moves through these groups in a simple path. The user opens "
            "a page. The page calls a typed function. The function sends a request "
            "to a router. The router calls a service. The service calls a "
            "repository. The repository reads the data and returns it back along "
            "the same path to the page, which then shows it to the user.",
        ]),
        ("Low Level Design", [
            "At a low level each group is broken into focused files. On the "
            "server the schemas define the shape of the data using Pydantic "
            "models. The services contain the rules, such as how to filter a list "
            "or how to score a suggested collaborator. The repositories contain "
            "the read logic for the current JSON source.",

            "On the client the types mirror the server schemas so the two sides "
            "agree on the shape of the data. The pages set the layout of each "
            "screen. The components, such as the researcher card and the stat "
            "card, are small and are reused across pages. A single client function "
            "exists for each server endpoint, which keeps all network calls in one "
            "clear place.",
        ]),
        ("Database Design", [
            "The data model follows an entity relationship design. Even though the "
            "first version stores data in JSON files, the shape of the data "
            "matches the tables that a real database will use later. The main "
            "entities and their key fields are shown in the table below.",
        ]),
        ("GUI Design", [
            "The interface follows the style of a clean university research "
            "portal, with the colours and identity of Bahria University. The home "
            "page opens with a search area and a row of live counts for "
            "researchers, publications, research areas, and projects. Below this "
            "it shows featured researchers and a grid of research areas.",

            "The researcher directory shows cards that can be filtered and "
            "searched. A profile page shows the biography, research areas, "
            "publications, and suggested collaborators of one person. The "
            "publications page, the research areas page, and the projects page "
            "each present their records in a clear list or grid. The collaboration "
            "page draws a small network that links a chosen researcher to others. "
            "The assistant page offers a chat style box for plain questions. Every "
            "page adjusts to smaller screens so the portal works on mobile as well "
            "as on desktop.",
        ]),
        ("External Interfaces", [
            "The main external interface is the web interface between the client "
            "and the server. The client sends requests to fixed addresses on the "
            "server, and the server returns data in JSON form. During development "
            "the client forwards these requests to the server through a local "
            "proxy, which keeps the setup simple.",

            "Two more external interfaces are used to prepare the data. One script "
            "reads the public faculty list and profile pages of the E-8 campus to "
            "build the researcher records. A second script queries the OpenAlex "
            "scholarly database to collect real publications for the faculty. Both "
            "scripts run on their own, away from the live system, so the running "
            "portal does not depend on any outside website.",
        ]),
    ],
}

# Data dictionary rows for the Database Design section (Table, Key Fields, Purpose).
DB_TABLE = [
    ("users", "user_id, email, role, is_active",
     "Login accounts for future use, with a role of researcher or admin."),
    ("researchers", "researcher_id, full_name, designation, department, orcid_id",
     "Profile of each faculty member of the campus."),
    ("publications", "publication_id, title, publication_year, journal_name, doi",
     "A paper written by one or more researchers."),
    ("authors", "author_id, full_name, orcid_id, affiliation",
     "A person listed as an author on a publication."),
    ("publication_authors", "publication_id, author_id, author_order",
     "Links publications to their authors in order."),
    ("topics", "topic_id, topic_name, description",
     "A research area used to group work, such as machine learning."),
    ("publication_topics", "publication_id, topic_id, confidence_score",
     "Links a publication to the topics it belongs to."),
    ("projects", "project_id, project_title, status, start_date, end_date",
     "A research project led by a principal investigator."),
    ("funding_sources", "funding_id, agency_name, country",
     "An agency that funds a project."),
    ("project_funding", "project_id, funding_id, amount, currency",
     "Links a project to its funding and amount."),
    ("collaboration_recommendations", "researcher_id, recommended_researcher_id, similarity_score",
     "A suggested collaborator based on shared topics."),
]

REFERENCES = [
    "Elsevier. Pure Research Information Management System. Elsevier B.V.",
    "Nazarbayev University. NU Research Portal. research.nu.edu.kz.",
    "VIVO Project. VIVO Open Source Research Networking Software. vivoweb.org.",
    "ORCID. Connecting Research and Researchers. orcid.org.",
    "DuraSpace. DSpace Repository Software. dspace.org.",
    "Bahria University. Department of Computer Science, E-8 Campus. bahria.edu.pk.",
]
