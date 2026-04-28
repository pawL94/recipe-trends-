"""
Recipe Trend Collector v2
Primaerquelle: TheMealDB (sauber, international, kostenlos)
Ergaenzung: Reddit Top-Posts
Ergebnis: trends.json mit 100 kuratierten Gerichten
"""

import os
import json
import re
import requests
from datetime import datetime, timezone

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TARGET_COUNT = 100

MEALDB_CATEGORIES = [
    "Beef", "Chicken", "Pasta", "Seafood", "Vegetarian",
    "Pork", "Lamb", "Miscellaneous", "Starter",
]

REDDIT_SUBREDDITS = [
    "recipes", "Cooking", "EatCheapAndHealthy", "MealPrepSunday", "GifRecipes",
]


def fetch_mealdb_recipes():
    all_meals = []
    for category in MEALDB_CATEGORIES:
        try:
            url = f"https://www.themealdb.com/api/json/v1/1/filter.php?c={category}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            meals = resp.json().get("meals") or []
            for meal in meals:
                all_meals.append(meal.get("strMeal", ""))
            print(f"TheMealDB {category}: {len(meals)} Rezepte")
        except Exception as e:
            print(f"TheMealDB {category}: {e}")
    return list(dict.fromkeys(all_meals))


def fetch_reddit_posts():
    headers = {"User-Agent": "RecipeTrendBot/2.0"}
    posts = []
    for subreddit in REDDIT_SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/top.json?t=week&limit=15"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            items = resp.json().get("data", {}).get("children", [])
            for item in items:
                post = item.get("data", {})
                if post.get("score", 0) >= 500:
                    posts.append(post.get("title", "").strip())
            print(f"Reddit r/{subreddit}: {len(items)} Posts")
        except Exception as e:
            print(f"Reddit {subreddit}: {e}")
    return posts


def curate_with_claude(mealdb_names, reddit_titles):
    if not ANTHROPIC_API_KEY:
        print("Kein API Key – nutze MealDB direkt")
        return mealdb_names[:TARGET_COUNT]

    mealdb_text = "\n".join([f"- {n}" for n in mealdb_names[:150]])
    reddit_text = "\n".join([f"- {t}" for t in reddit_titles[:50]])

    prompt = f"""Du bist ein Kulinarik-Experte. Erstelle eine Liste der 100 bekanntesten internationalen Gerichte.

DATENBASIS A - Internationale Klassiker (TheMealDB):
{mealdb_text}

DATENBASIS B - Aktuelle Reddit-Trends (Rohtitel):
{reddit_text}

AUFGABE:
1. Waehle hauptsaechlich aus Datenbasis A - bevorzuge bekannte Klassiker
2. Ergaenze aus B nur echte etablierte Gerichte mit klarem Namen
3. Uebersetze ins Deutsche wo sinnvoll (Spaghetti Carbonara, Wiener Schnitzel etc.)
4. Sortiere nach globaler Bekanntheit

NICHT aufnehmen:
- Generisch: "Haehnchen-Pfanne", "Gemuese-Suppe", "Fleisch mit Reis"
- Indisches Streetfood: Paratha, Samosa, Kachori, Pakoda, Roti, Bhindi
- Getraenke, Snacks, Suessigkeiten (ausser Dessert-Klassiker wie Tiramisu)
- Nicht in Deutschland nachkochbar

ZIELVERTEILUNG: 35% Europaeisch, 25% Asiatisch, 20% Amerikanisch, 20% Rest

Antworte NUR mit JSON-Array:
["Pasta Carbonara", "Shakshuka", "Butter Chicken", "Wiener Schnitzel"]"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )
        if resp.status_code == 200:
            text = resp.json()["content"][0]["text"]
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                recipes = json.loads(match.group())
                print(f"Claude: {len(recipes)} Rezepte kuratiert")
                return recipes
    except Exception as e:
        print(f"Claude Fehler: {e}")

    return mealdb_names[:TARGET_COUNT]


def main():
    print(f"Recipe Trend Collector v2 - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    print("\nTheMealDB...")
    mealdb_names = fetch_mealdb_recipes()
    print(f"   {len(mealdb_names)} Rezepte")

    print("\nReddit...")
    reddit_titles = fetch_reddit_posts()
    print(f"   {len(reddit_titles)} Posts")

    print("\nKuratierung...")
    recipes = curate_with_claude(mealdb_names, reddit_titles)

    output = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_date": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
        "count": len(recipes),
        "source": "TheMealDB + Reddit (kuratiert von Claude)",
        "recipes": recipes,
    }

    output_path = os.path.join(os.path.dirname(__file__), "..", "trends.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nErgebnis: {len(recipes)} Rezepte gespeichert")
    print("\nTop 15:")
    for i, r in enumerate(recipes[:15], 1):
        print(f"  {i:2d}. {r}")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
