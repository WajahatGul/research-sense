"# research-sense" 

Questions like:
• Where does your data actually come from, and how does it enter your system?
• Walk me through the complete lifecycle of a request, from the moment a user clicks "Generate" until the response appears on the screen.
• Why did you choose a RAG pipeline for this project? Why wasn't a simple database query or fine-tuning enough?
• What information lives in PostgreSQL, and what belongs in your vector database? Why split them?
• How are documents processed before they become searchable? Explain your ingestion pipeline.
• How do you chunk data? Why that chunk size? What happens if the document is too large?
• How do you prevent the LLM from hallucinating when working with business-critical data?
• If your retrieval step fails, what does the system do?
• How would this architecture change if the dataset grew from hundreds of documents to millions?
• Which parts of the system are stateless? Which parts maintain state?
• If you had to deploy this for thousands of users tomorrow, what would you redesign first?
• Forget the team. What exactly did you build?