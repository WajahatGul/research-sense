"""Text content for the ResearchSense FYP report (Chapters 1 to 4).

All prose is written in plain English and is original to this project. Dashes
are avoided on purpose. Placeholders in square brackets are for the student to
fill before submission.
"""

TITLE = "ResearchSense: A Research Information System for Bahria University"
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
    "University, covering the computing faculty of its Islamabad (E-8 and H-11), "
    "Karachi and Lahore campuses. Universities produce a large amount of "
    "research every year, but the records of researchers, publications, and "
    "projects are often spread across separate files and web pages. This makes "
    "it hard for students, faculty, and outside visitors to find who works on a "
    "topic or what work the campus has produced.",

    "ResearchSense brings this information into one clear place. It offers "
    "researcher profiles, a searchable list of publications, a set of research "
    "areas, funded projects, a tool that suggests possible collaborators using "
    "real co authorship records, an analytics dashboard, and a grounded "
    "assistant that answers plain language questions using only the data held "
    "by the system. Faculty members can sign in with a verified identity, add "
    "their own publications, and add any paper of interest to a shared library "
    "so the assistant can answer questions about it. The system uses a React "
    "and TypeScript interface with a FastAPI service behind it.",

    "The design keeps the research data separate from the parts of the system "
    "that change often, such as accounts and uploads, which already live in a "
    "real database. Because of this separation, the read only research records "
    "can later move to a full relational database without changing the pages "
    "or the business logic. This report presents the background, the review of "
    "similar systems, the requirements, and the design of ResearchSense.",
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

            "At present the research record of Bahria University is hard to view "
            "as a whole. Faculty details sit on one set of pages, spread across "
            "separate campuses, while publication lists, if they exist, sit "
            "somewhere else or on personal profiles on outside websites. A visitor "
            "who wants to know which teachers work on machine learning, or how many "
            "papers a campus has produced in a field, has no single place to look.",

            "ResearchSense is a research information system that solves this "
            "problem. It collects the profiles of researchers, their publications, "
            "the topics they study, and the projects they lead, and it presents "
            "all of this through one clean web portal. Faculty members can claim "
            "their own profile, sign in, and keep their publication record up to "
            "date, while any visitor can search the portal or ask a built in "
            "assistant a plain question and receive an answer grounded in the "
            "system's own records. The idea follows the style of well known "
            "university research portals, but it is shaped for the needs of "
            "Bahria University and uses the real computing faculty of its four "
            "teaching campuses as its data.",
        ]),
        ("Problem Description", [
            "The main problem is that research information at the campus is "
            "scattered and hard to search. This creates several smaller problems.",

            "First, students and new researchers cannot easily find a supervisor "
            "or a partner who shares their interests. They have to ask people by "
            "hand or read many separate pages. Second, the campus cannot show its "
            "research strength in a clear way, because there is no single view of "
            "how many researchers, papers, and projects it has. Third, useful "
            "links between people who study the same topic, or who have already "
            "written papers together, stay hidden, so chances for teamwork are "
            "missed. Fourth, there is no simple way to ask a plain question, such "
            "as who works on cybersecurity or whether two named researchers have "
            "worked together, and get a direct, trustworthy answer. Fifth, "
            "keeping a faculty publication record current usually means asking an "
            "office administrator to update a page by hand, which is slow and "
            "easy to neglect.",

            "ResearchSense is built to remove these gaps by placing all the "
            "information in one searchable and connected system, and by letting "
            "faculty members maintain their own record directly.",
        ]),
        ("Project Objectives", [
            "The objectives of the project are listed below.",
        ], [
            "Build one web portal that shows researcher profiles, publications, "
            "research areas, and projects for the campus.",
            "Make the information easy to search and filter by name, department, "
            "designation, topic, campus, and year.",
            "Show the research strength of the campus through clear counts, "
            "featured profiles, and an analytics dashboard of trends over time.",
            "Suggest possible collaborators by combining real co authored "
            "publications with shared research topics, and let a visitor filter "
            "suggestions by campus or by area.",
            "Provide a grounded assistant that answers plain language questions "
            "using only the system's own records, points the user to the right "
            "people, papers, and areas, and declines to answer when it has no "
            "supporting evidence rather than guessing.",
            "Let a faculty member claim their own profile with a verified "
            "identity, sign in, add new publications, upload their own papers, "
            "and add any paper of interest to a shared library for the assistant "
            "to read and answer questions about.",
            "Give an administrator a simple way to review accounts and refresh "
            "the underlying research data on demand.",
            "Keep the read only research records behind a clear boundary so that "
            "a full relational database can be added later without a rewrite of "
            "the system.",
        ]),
        ("Project Scope", [
            "ResearchSense delivers a complete, working portal together with a "
            "grounded conversational assistant. The data for this version comes "
            "from the real computing faculty (Computer Science, Software "
            "Engineering, and Computer Engineering) across the four campuses, "
            "including real emails, research areas, and qualifications, together "
            "with real publications collected from the OpenAlex scholarly "
            "database and matched to their real authors. Project and funding "
            "records are sample values that are clearly marked as sample. The "
            "system runs as a web application that any modern browser can open.",

            "Within this scope, faculty members can claim their profile using "
            "their ORCID identifier, which is checked against the public ORCID "
            "registry so that a profile can only be claimed by the person it "
            "belongs to. Once signed in, a faculty member can add a new "
            "publication by entering its DOI, which the system uses to fetch "
            "and verify the paper's details, or by entering the details by hand "
            "when no DOI exists. A new publication is only accepted once the "
            "system has confirmed that the signed in researcher is really one of "
            "its authors, so that a record cannot be added to the wrong profile. "
            "A faculty member can also upload their own paper so that the "
            "assistant can read its full text, and can separately add any paper "
            "of interest, whether or not they wrote it, to a shared library that "
            "the assistant can read without attaching it to anyone's profile. An "
            "administrator can review accounts and trigger a refresh of the "
            "research data on demand.",

            "The assistant itself answers from the researcher, publication, "
            "project, topic, and co authorship records, and from the full text "
            "of uploaded and library papers, and it clearly declines to answer a "
            "question that its records do not support. Two kinds of question, "
            "who wrote a given paper and whether two named people have worked "
            "together, are answered directly from the structured records rather "
            "than left to open ended generation, so that these common questions "
            "get precise and checkable answers.",

            "The following items are left for future work and are not part of "
            "this version: a full relational database for the read only research "
            "records (which currently live in structured files while accounts "
            "and uploads already live in a real database), automatic extraction "
            "of a researcher's teaching timetable or office details, and support "
            "for languages other than English. The current design leaves a "
            "clean place for each of these to be added without changing the "
            "parts that are already built.",
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

            "A separate line of recent work looks at retrieval augmented "
            "generation, a method where a language model answers a question "
            "using text retrieved from a trusted collection rather than from its "
            "own general training alone. This method is well suited to a "
            "research portal, because it lets an assistant answer from a "
            "university's own verified records and decline a question that those "
            "records do not cover, instead of inventing an answer.",
        ]),
        ("Gaps and the Need for ResearchSense", [
            "From this review three points stand out. The paid systems are strong "
            "but costly and heavy for a single campus. The free systems are open "
            "but need real effort to run and often look plain. The personal "
            "profile services are helpful but do not give a campus wide view.",

            "There is also a common gap in local discovery and interaction. Few of "
            "these tools, in their basic form, combine real co authorship "
            "evidence with shared research interests to suggest who a researcher "
            "could work with, and few let a user ask a plain question and "
            "receive an answer that is both grounded in the institution's own "
            "data and honest about what it does not know. For a single "
            "department that wants a clear, attractive, low cost portal with "
            "these abilities, none of the existing options fits well on its own.",

            "ResearchSense aims to fill this gap. It offers a clean and modern "
            "portal shaped for one campus, it links researchers by shared topics "
            "and by real co authored papers to support teamwork, it lets faculty "
            "maintain their own verified record, and it includes a grounded "
            "assistant for plain questions that refuses to guess when its records "
            "do not support an answer. It is built with a clear separation "
            "between the interface, the logic, and the data, so it stays easy to "
            "maintain and to extend.",
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
            "are usually kept in office files and are not shown online. Keeping "
            "any of this current depends on an administrator updating a page by "
            "hand whenever something changes.",

            "This existing setup has clear drawbacks. The information is spread "
            "out, so a full view is missing. Search is weak or absent, so finding "
            "a person by topic is slow. Links between researchers who share "
            "interests, or who have already written papers together, are not "
            "shown at all. There is no way to ask a plain question and get a "
            "direct, checkable answer. Because the parts are not connected, the "
            "campus cannot present its research as one clear story.",
        ]),
        ("Proposed System", [
            "The proposed system, ResearchSense, replaces the scattered setup with "
            "one connected portal. It stores researchers, publications, topics, "
            "and projects in a single model and shows them through linked pages. "
            "A visitor can start from the home page, move to a researcher profile, "
            "see that person's papers and topics, and then jump to a suggested "
            "collaborator, all without leaving the portal.",

            "The proposed system adds features that the existing setup does not "
            "have. It counts the research output of the campus and shows it on "
            "the home page and on an analytics dashboard. It lets users filter "
            "people and papers in many ways. It suggests collaborators by "
            "combining real co authored publications with shared topics, and "
            "lets a visitor narrow the suggestions to the same campus, another "
            "campus, or a chosen research area. It lets a faculty member claim "
            "their profile with a verified identity, sign in, add new "
            "publications by DOI or by hand, upload their own papers, and add "
            "any paper of interest to a shared library. It offers a grounded "
            "assistant that turns a plain question into a helpful answer with "
            "links, and that answers questions about authorship and about "
            "collaboration directly from the structured records so that these "
            "common questions are precise rather than approximate.",
        ]),
        ("Functional Requirements", [
            "The functional requirements describe what the system must do.",
        ], [
            "The system shall show a home page with search, live counts, featured "
            "researchers, and a list of research areas.",
            "The system shall list all researchers and allow filtering by "
            "department, designation, campus, and topic, and searching by name.",
            "The system shall show a full profile for each researcher, including "
            "biography, research areas, publications, and suggested collaborators.",
            "The system shall list publications and allow filtering by year and "
            "topic and searching by title, and shall let a user open the paper "
            "itself or ask the assistant about it.",
            "The system shall list research areas and show how many publications "
            "and researchers belong to each area.",
            "The system shall list funded projects with their status, dates, lead "
            "researcher, and funding details.",
            "The system shall show a collaboration view that ranks suggested "
            "collaborators for a chosen researcher first by real co authored "
            "publications and then by shared research areas, and shall let the "
            "user filter by campus and by area.",
            "The system shall show an analytics dashboard of publication counts "
            "over time, citation growth, leading venues, and cross campus "
            "collaboration.",
            "The system shall let a faculty member claim their profile using an "
            "ORCID identifier that is checked against the public ORCID registry, "
            "choose a password, and sign in afterward with the same credentials.",
            "The system shall let a signed in faculty member submit a new "
            "publication by entering its DOI, automatically fetch and display the "
            "paper's details for confirmation, warn when the paper is already on "
            "record, and accept the submission only once the signed in "
            "researcher is confirmed to be one of its authors.",
            "The system shall let a signed in faculty member submit a new "
            "publication by hand when no DOI exists, recording the same core "
            "details as a DOI based submission.",
            "The system shall let a signed in faculty member upload a paper of "
            "their own so that the assistant can read and answer questions about "
            "its full text.",
            "The system shall let a signed in faculty member add any paper of "
            "interest, whether authored by them or not, to a shared library, "
            "either by DOI or by uploading a file, so the assistant can read it "
            "without attributing it to any profile.",
            "The system shall let an administrator sign in separately from "
            "faculty members, view and activate or deactivate accounts, and "
            "trigger a refresh of the underlying research data.",
            "The system shall provide an assistant that accepts a plain question "
            "and returns an answer with links to relevant people, papers, and "
            "areas, using only the system's own records.",
            "The assistant shall decline to answer a question that its records "
            "do not support, rather than inventing an answer.",
            "The assistant shall answer a question about who wrote a given paper, "
            "and a question about whether two named researchers have worked "
            "together, directly from the structured publication and authorship "
            "records.",
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
            "Extensibility: the read only research data shall sit behind a clear "
            "boundary so a full relational database can be added later with "
            "little change elsewhere.",
            "Reliability: when a service cannot be reached, the interface shall "
            "show a clear message instead of failing without notice.",
            "Security: a profile shall only be claimed after its owner's ORCID "
            "identity has been checked, passwords shall be stored using a salted "
            "one way hash rather than in plain text, and faculty and "
            "administrator sign in shall be kept separate.",
            "Trustworthiness: the assistant shall only state facts that are "
            "present in the system's own records and shall say so plainly when a "
            "question falls outside what it has been given.",
        ]),
        ("Use Cases", [
            "The main users of the system are the visitor, who can be a student, "
            "a faculty member browsing anonymously, or an outside guest, the "
            "signed in faculty member, who manages their own profile and "
            "records, and the administrator, who oversees accounts and the "
            "underlying data. The key use cases for the current version are "
            "listed below.",
        ], [
            "Search for a researcher by name or by research area.",
            "Browse the researcher directory and apply filters.",
            "View a researcher profile and open a suggested collaborator.",
            "Browse and filter publications by year and topic, and open a paper "
            "or ask the assistant about it.",
            "Explore research areas and open the work under an area.",
            "View funded projects and their funding details.",
            "View the analytics dashboard for campus wide research trends.",
            "Claim a faculty profile with a verified ORCID identifier and sign "
            "in.",
            "Submit a new publication by DOI, confirm its details, and have it "
            "added once authorship is verified.",
            "Submit a new publication by hand when no DOI exists.",
            "Upload a personal paper so the assistant can read its full text.",
            "Add any paper of interest to the shared library, by DOI or by "
            "upload, for the assistant to read.",
            "Sign in as an administrator, review accounts, and trigger a data "
            "refresh.",
            "Ask the assistant a plain question and follow its links, including "
            "questions about who wrote a paper or whether two researchers have "
            "collaborated.",
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
            "and shows the results. The client never reads a data source "
            "directly; it only speaks to the server through a small set of typed "
            "functions.",

            "On the server the work flows through four clear layers. A router "
            "receives each request. A service holds the business logic. A "
            "repository reads and writes the data. A data source holds the actual "
            "records. The research corpus, meaning researchers, publications, "
            "projects, and topics, is held in structured files, while accounts "
            "and uploads, which change often and must stay private, already live "
            "in a small real database. Because each repository hides its data "
            "source behind a fixed boundary, the research corpus can later move "
            "into a full relational database while the routers and services stay "
            "the same.",

            "A separate part of the server supports the assistant. A retrieval "
            "component turns the research corpus and any uploaded or library "
            "paper text into searchable passages and finds the passages closest "
            "in meaning to a user's question. A generation component then writes "
            "an answer using only those passages, or declines to answer when "
            "nothing relevant is found. Two direct lookups sit in front of this "
            "general path, answering authorship questions and collaboration "
            "questions straight from the structured publication records when a "
            "question clearly asks for one of these, since a precise, checkable "
            "answer is better than an approximate one for these common cases.",
        ]),
        ("Design Constraints", [
            "The design works within a few constraints. Publications are real and "
            "come from the OpenAlex scholarly database, matched to Bahria "
            "affiliated authors, and are supplemented by publications that "
            "faculty members submit themselves once their authorship has been "
            "confirmed. Project and funding records are sample data, since the "
            "campus does not publish these in a single feed, and they are marked "
            "as sample so their origin is always clear.",

            "The assistant depends on a hosted large language model service "
            "reached over the internet for the parts of its answer that need "
            "natural language generation, so a question can only be answered "
            "generatively while that service is reachable. To reduce the effect "
            "of any single provider being temporarily unavailable, the system is "
            "written to try more than one model in turn before giving up on a "
            "generative answer. The direct authorship and collaboration lookups "
            "do not depend on this service at all, since they read the "
            "structured records directly.",

            "A further constraint is set by the team itself. Every source file is "
            "kept small, with one clear purpose, so the code stays easy to read "
            "and to change. This rule shapes how the pages and the server modules "
            "are divided.",
        ]),
        ("Design Methodology", [
            "The project uses an object based and component based method. On the "
            "server, each resource, such as a researcher, a publication, an "
            "account, or a library paper, has its own schema, service, and "
            "repository. On the client, the interface is built from small "
            "reusable components that are grouped into feature folders and page "
            "folders.",

            "The guiding ideas are separation of concerns, loose coupling, and "
            "high cohesion. Separation of concerns means each part has one job. "
            "Loose coupling means parts depend on each other as little as "
            "possible. High cohesion means the pieces inside one part belong "
            "together. A related idea used in the assistant is to prefer a "
            "direct, structured answer over a generated one whenever a question "
            "can be answered precisely from existing records, and to fall back "
            "to grounded generation only when a direct answer is not available. "
            "These ideas together make the system easier to test, to trust, and "
            "to grow.",
        ]),
        ("High Level Design", [
            "At a high level the system has four groups of parts. The first "
            "group is the client interface, which holds the pages, the shared "
            "components, and the typed functions that call the server. The "
            "second group is the server logic, which holds the routers and the "
            "services for researchers, publications, projects, topics, accounts, "
            "and submissions. The third group is data access, which holds the "
            "repositories, the research corpus files, and the small database "
            "used for accounts and uploads. The fourth group is the assistant, "
            "which holds the retrieval component, the direct authorship and "
            "collaboration lookups, and the generation component.",

            "A typical request moves through these groups in a simple path. The "
            "user opens a page. The page calls a typed function. The function "
            "sends a request to a router. The router calls a service. The "
            "service calls a repository, or, for a question to the assistant, "
            "calls the retrieval component and then either a direct lookup or "
            "the generation component. The result returns back along the same "
            "path to the page, which then shows it to the user.",
        ]),
        ("Low Level Design", [
            "At a low level each group is broken into focused files. On the "
            "server the schemas define the shape of the data using Pydantic "
            "models. The services contain the rules, such as how to filter a "
            "list, how to score a suggested collaborator, how to verify that a "
            "submitted paper's author list includes the signed in researcher, or "
            "how to check an ORCID identifier against the public registry before "
            "a profile can be claimed. The repositories contain the read and "
            "write logic for the current data sources.",

            "The assistant is split into a retrieval module, which turns text "
            "into searchable form and ranks passages by closeness to a question, "
            "and a generation module, which writes the final answer strictly "
            "from the passages it is given. The direct authorship and "
            "collaboration lookups sit alongside these and are checked first for "
            "the kinds of question they cover.",

            "On the client the types mirror the server schemas so the two sides "
            "agree on the shape of the data. The pages set the layout of each "
            "screen. The components, such as the researcher card and the stat "
            "card, are small and are reused across pages. A single client "
            "function exists for each server endpoint, which keeps all network "
            "calls in one clear place.",
        ]),
        ("Database Design", [
            "ResearchSense uses two kinds of storage today. Researchers, "
            "publications, projects, and topics form the read only research "
            "corpus and follow an entity relationship design even though they "
            "currently live in structured files, so the shape of the data "
            "already matches the tables that a full relational database will use "
            "later. Accounts and uploads change often, must stay private, and "
            "already live in a small real database. The main entities and their "
            "key fields are shown in the table below.",
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
            "each present their records in a clear list or grid, and a "
            "publication can be opened directly or handed to the assistant. The "
            "collaboration page draws a network that links a chosen researcher "
            "to others, marking those with real co authored papers differently "
            "from those who only share a research area, and can be filtered by "
            "campus or by area. The analytics page shows charts of publication "
            "and citation trends. The library page lists every paper that has "
            "been added for the assistant to read, whether or not it belongs to "
            "a profile. The portal page lets a faculty member claim a profile, "
            "sign in, submit publications, upload papers, and add papers to the "
            "library, and lets an administrator manage accounts and refresh the "
            "data. The assistant page offers a chat style box for plain "
            "questions. Every page adjusts to smaller screens so the portal "
            "works on mobile as well as on desktop.",
        ]),
        ("External Interfaces", [
            "The main external interface is the web interface between the client "
            "and the server. The client sends requests to fixed addresses on the "
            "server, and the server returns data in JSON form.",

            "Several outside services support the research data and the "
            "assistant. Scripts read the public faculty directory of the "
            "university to build the researcher records for every campus, and "
            "query the OpenAlex scholarly database to collect real publications "
            "and, when a researcher's identity is confirmed, their co authored "
            "papers. When a faculty member submits a publication by DOI, the "
            "system queries scholarly metadata services to fetch and verify the "
            "paper's title, authors, and venue, and consults the public ORCID "
            "registry to confirm a claimed identity before a profile can be "
            "taken. When a paper is added to the shared library by DOI, the "
            "system looks for an openly available copy of the paper to read its "
            "full text. The assistant reaches a hosted large language model "
            "service to write its generated answers, while its direct authorship "
            "and collaboration answers do not need this service at all. These "
            "outside calls are isolated behind their own modules so the rest of "
            "the system does not depend on the details of any one outside "
            "service.",
        ]),
    ],
}

# Data dictionary rows for the Database Design section (Table, Key Fields, Purpose).
DB_TABLE = [
    ("accounts", "orcid_id, researcher_id, password_hash, active",
     "A faculty login, created once a profile is claimed with a verified "
     "ORCID identifier."),
    ("uploads", "id, researcher_id, title, filename, uploaded_at",
     "A record of a paper a faculty member has uploaded for the assistant "
     "to read."),
    ("researchers", "researcher_id, full_name, designation, department, orcid_id",
     "Profile of each faculty member of the campus."),
    ("publications", "publication_id, title, publication_year, journal_name, doi",
     "A paper written by one or more researchers, whether collected from "
     "OpenAlex or submitted by a faculty member."),
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
    ("collaboration_recommendations",
     "researcher_id, recommended_researcher_id, shared_publications, "
     "similarity_score",
     "A suggested collaborator, ranked by real co authored publications "
     "and by shared topics."),
]

REFERENCES = [
    "Elsevier. Pure Research Information Management System. Elsevier B.V.",
    "Nazarbayev University. NU Research Portal. research.nu.edu.kz.",
    "VIVO Project. VIVO Open Source Research Networking Software. vivoweb.org.",
    "ORCID. Connecting Research and Researchers. orcid.org.",
    "DuraSpace. DSpace Repository Software. dspace.org.",
    "Bahria University. Faculty Directory. bahria.edu.pk/Home/Faculty.",
    "OpenAlex. An Open Catalog of Scholarly Works. openalex.org.",
    "Lewis, P. et al. Retrieval Augmented Generation for Knowledge Intensive "
    "NLP Tasks. Advances in Neural Information Processing Systems, 2020.",
]
