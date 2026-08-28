"""Test rapide du SDK officiel parallel-web."""
import os
from dotenv import load_dotenv
from parallel import Parallel

load_dotenv()  # charge ton .env local (PARALLEL_API_KEY)

client = Parallel(api_key=os.environ.get("PARALLEL_API_KEY"))

search = client.search(
    objective="Verifier que le SDK Parallel fonctionne",
    search_queries=["Cameroon film production drone regulation CCAA"],
)

print("=== RESULTATS ===")
for result in search.results[:3]:
    print(f"- {result.title}")
    print(f"  {result.url}")
print("=== SDK PARALLEL OK ===")