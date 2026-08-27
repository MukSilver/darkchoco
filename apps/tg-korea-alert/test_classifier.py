import argparse
import asyncio
import os

from company_country_classifier import CompanyCountryClassifier
from korea_alert_monitor import DEFAULT_DB_PATH, open_database, post_discord
from local_config import load_local_env, normalize_discord_webhook


SAMPLES = [
    (
        "Keyword/domain",
        "Ransomware alert\nCountry: South Korea\nCompany: Example Corp",
    ),
    (
        "DART",
        "Ransomware victim\nCompany: \uC0BC\uC131\uC804\uC790\nFiles will be published",
    ),
    (
        "Gemini",
        "Ransomware victim\nCompany: Samsung SDS\nFiles will be published",
    ),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Test all Korea company classification stages.")
    parser.add_argument("--discord", action="store_true", help="Send the test summary to Discord")
    return parser.parse_args()


async def main(args):
    load_local_env()
    database = open_database(DEFAULT_DB_PATH)
    try:
        classifier = CompanyCountryClassifier(
            database,
            os.environ["DART_API_KEY"],
            os.environ["GEMINI_API_KEY"],
        )
        await classifier.initialize()
        results = []
        for label, text in SAMPLES:
            result = await classifier.classify(text)
            results.append((label, result))
            print(
                f"{label}: korean={result.is_korean}, source={result.source}, "
                f"confidence={result.confidence:.0%}"
            )

        if args.discord:
            lines = ["**[PIPELINE TEST] Korea company classification**", ""]
            for label, result in results:
                company = result.company_name or "-"
                lines.append(
                    f"{label}: is_korean={result.is_korean}, source={result.source}, "
                    f"confidence={result.confidence:.0%}, company={company}"
                )
            webhook_url = normalize_discord_webhook(os.environ["DISCORD_WEBHOOK_URL"])
            await asyncio.to_thread(post_discord, webhook_url, "\n".join(lines))
            print("Discord pipeline test sent successfully.")
    finally:
        database.close()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
