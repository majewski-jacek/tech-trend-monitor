import math
import re
from typing import Dict, List, Set, Tuple


class SentimentAnalyzer:
    """Fast, accurate rule-based sentiment and tech trend analyzer."""

    # Lexicon with domain-specific tech and general sentiment weights
    LEXICON: Dict[str, float] = {
        # Positive tech & general words
        "breakthrough": 3.2,
        "breakthroughs": 3.2,
        "revolutionary": 3.0,
        "innovative": 2.8,
        "innovation": 2.8,
        "innovations": 2.8,
        "excellence": 2.8,
        "excellent": 2.7,
        "outstanding": 2.7,
        "wonderful": 2.6,
        "awesome": 2.6,
        "amazing": 2.6,
        "boost": 2.2,
        "boosts": 2.2,
        "gain": 2.0,
        "gains": 2.0,
        "faster": 2.4,
        "fast": 2.0,
        "speedup": 2.5,
        "speedups": 2.5,
        "efficient": 2.3,
        "scalable": 2.2,
        "secure": 2.2,
        "improvement": 2.1,
        "improvements": 2.2,
        "improve": 2.0,
        "improved": 2.0,
        "success": 2.5,
        "successful": 2.4,
        "great": 2.2,
        "good": 1.8,
        "best": 2.5,
        "better": 1.8,
        "love": 2.5,
        "loved": 2.4,
        "solution": 1.6,
        "solutions": 1.6,
        "fix": 1.8,
        "fixed": 1.8,
        "fixes": 1.8,
        "resolved": 1.9,
        "stable": 2.0,
        "stability": 2.0,
        "release": 1.2,
        "releases": 1.2,
        "launch": 1.5,
        "upgrade": 2.0,
        "upgrades": 2.0,
        "supercharged": 2.8,
        "clean": 1.7,
        "elegant": 2.2,
        "delight": 2.5,
        "delightful": 2.5,
        "powerful": 2.3,
        "promising": 2.0,
        "profit": 2.0,
        "growth": 2.0,
        "optimizing": 2.1,
        "optimized": 2.2,
        "optimization": 2.2,
        "optimizations": 2.2,
        "win": 2.4,
        "wins": 2.4,
        "winning": 2.4,
        "award": 2.3,
        "heroic": 2.5,
        "free": 1.2,
        "open-source": 1.5,
        "reliable": 2.2,
        
        # Negative tech & general words
        "vulnerability": -3.5,
        "vulnerabilities": -3.5,
        "vulnerable": -3.2,
        "exploit": -3.5,
        "exploited": -3.5,
        "exploits": -3.5,
        "breach": -3.6,
        "breaches": -3.6,
        "hacked": -3.4,
        "attack": -3.2,
        "attacks": -3.2,
        "attacker": -3.0,
        "malware": -3.8,
        "ransomware": -4.0,
        "critical": -2.6,
        "bug": -2.2,
        "bugs": -2.2,
        "flaw": -2.5,
        "flaws": -2.5,
        "crash": -3.0,
        "crashed": -3.0,
        "crashes": -3.0,
        "failing": -2.8,
        "failed": -2.8,
        "failure": -3.0,
        "failures": -3.0,
        "broken": -2.8,
        "break": -1.8,
        "slow": -2.2,
        "slowdown": -2.4,
        "sluggish": -2.3,
        "leak": -2.8,
        "leaked": -2.8,
        "leaks": -2.8,
        "outage": -3.4,
        "outages": -3.4,
        "down": -2.0,
        "downtime": -3.0,
        "lawsuit": -2.8,
        "sued": -2.8,
        "ban": -2.5,
        "banned": -2.5,
        "risk": -2.2,
        "risks": -2.2,
        "risky": -2.4,
        "threat": -3.0,
        "threats": -3.0,
        "terrible": -3.2,
        "bad": -2.2,
        "worst": -3.5,
        "awful": -3.2,
        "deprecate": -1.8,
        "deprecated": -2.0,
        "kill": -2.5,
        "killed": -2.5,
        "loss": -2.4,
        "losses": -2.4,
        "lost": -2.2,
        "drop": -1.8,
        "damage": -2.8,
        "damaged": -2.8,
        "chaos": -3.0,
        "scam": -3.8,
        "scams": -3.8,
        "fraud": -3.8,
        "layoffs": -3.0,
        "layoff": -3.0,
        "danger": -2.8,
        "dangerous": -2.9,
    }

    # Negation words that invert subsequent sentiment within a 3-word window
    NEGATIONS: Set[str] = {
        "not", "no", "never", "neither", "hardly", "scarcely", "barely",
        "without", "don't", "dont", "wasn't", "wasnt", "isn't", "isnt",
        "aren't", "arent", "cannot", "can't", "cant", "won't", "wont"
    }

    # Modifiers that scale the next word's intensity
    BOOSTERS: Dict[str, float] = {
        "very": 1.5,
        "extremely": 1.8,
        "massive": 1.6,
        "hugely": 1.6,
        "huge": 1.5,
        "significantly": 1.5,
        "highly": 1.4,
        "super": 1.5,
        "really": 1.3,
        "major": 1.4,
        "slightly": 0.6,
        "somewhat": 0.7,
        "barely": 0.5,
    }

    # Standardized Tech Taxonomy for Tag Extraction
    TECH_TAXONOMY: Dict[str, List[str]] = {
        "AI": ["ai", "artificial intelligence", "machine learning", "deep learning", "neural"],
        "LLM": ["llm", "large language model", "chatgpt", "gpt-4", "gpt", "gemini", "claude", "anthropic", "openai", "llama"],
        "Python": ["python", "pydantic", "fastapi", "django", "flask", "numpy", "pandas", "pytorch"],
        "Rust": ["rust", "cargo", "rustlang"],
        "JavaScript": ["javascript", "js", "node.js", "nodejs", "npm", "deno", "bun"],
        "TypeScript": ["typescript", "ts"],
        "Go": ["golang", "go language", "go 1."],
        "Cloud": ["cloud", "aws", "azure", "gcp", "google cloud", "serverless", "lambda"],
        "DevOps": ["devops", "docker", "kubernetes", "k8s", "ci/cd", "terraform", "ansible"],
        "Security": ["security", "cve", "vulnerability", "exploit", "breach", "ransomware", "malware", "cybersecurity", "zero-day", "encryption"],
        "Web": ["react", "vue", "svelte", "next.js", "nextjs", "tailwind", "css", "html", "webassembly", "wasm"],
        "Database": ["database", "postgres", "postgresql", "sqlite", "mysql", "redis", "mongodb", "sql"],
        "Linux": ["linux", "kernel", "ubuntu", "debian", "arch", "fedora"],
        "Architecture": ["microservices", "distributed systems", "api", "graphql", "rest", "concurrency", "performance"]
    }

    STOPWORDS: Set[str] = {
        "the", "and", "a", "an", "in", "on", "of", "to", "for", "with", "at",
        "by", "from", "up", "about", "into", "over", "after", "is", "are", "was",
        "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "shall", "should", "may", "might", "must", "can", "could",
        "it", "its", "that", "this", "these", "those", "which", "what", "who", "whom",
        "how", "when", "where", "why", "all", "any", "both", "each", "few", "more",
        "most", "other", "some", "such", "than", "too", "very", "show", "hn", "ask", "tell"
    }

    @classmethod
    def analyze_sentiment(cls, text: str) -> Tuple[float, str]:
        """
        Calculates sentiment score between -1.0 and 1.0 and returns (score, label).
        Uses lexicon weights, negation detection, and booster scaling.
        """
        if not text:
            return 0.0, "Neutral"

        clean_text = text.lower()
        words = re.findall(r"\b[a-z0-9\-']+\b", clean_text)
        if not words:
            return 0.0, "Neutral"

        scores: List[float] = []
        n_words = len(words)

        for i, word in enumerate(words):
            word_score = 0.0
            # Check single word
            if word in cls.LEXICON:
                word_score = cls.LEXICON[word]
            
            if word_score != 0.0:
                # Check for booster in previous word
                if i > 0 and words[i - 1] in cls.BOOSTERS:
                    word_score *= cls.BOOSTERS[words[i - 1]]
                
                # Check for negation in 1-3 previous tokens
                negated = False
                for j in range(max(0, i - 3), i):
                    if words[j] in cls.NEGATIONS:
                        negated = True
                        break
                
                if negated:
                    word_score = -0.75 * word_score

                scores.append(word_score)

        if not scores:
            return 0.0, "Neutral"

        total_sum = sum(scores)
        # Normalization function similar to VADER compound calculation
        # compound = sum / sqrt(sum^2 + alpha)
        alpha = 15.0
        compound = total_sum / math.sqrt((total_sum * total_sum) + alpha)
        compound = round(max(-1.0, min(1.0, compound)), 3)

        if compound >= 0.05:
            label = "Positive"
        elif compound <= -0.05:
            label = "Negative"
        else:
            label = "Neutral"

        return compound, label

    @classmethod
    def extract_tags(cls, text: str) -> List[str]:
        """Extract matching tech taxonomy tags from text."""
        if not text:
            return []

        lower_text = text.lower()
        matched_tags: List[str] = []

        for category, patterns in cls.TECH_TAXONOMY.items():
            for pattern in patterns:
                # Exact word or phrase boundary match
                escaped = re.escape(pattern)
                regex = rf"\b{escaped}\b"
                if re.search(regex, lower_text):
                    if category not in matched_tags:
                        matched_tags.append(category)
                    break

        return matched_tags

    @classmethod
    def extract_keywords(cls, text: str, max_keywords: int = 5) -> List[str]:
        """Extract top representative keywords from text excluding common stopwords."""
        if not text:
            return []

        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        meaningful = [w for w in words if w not in cls.STOPWORDS and len(w) >= 3]

        freq: Dict[str, int] = {}
        for w in meaningful:
            freq[w] = freq.get(w, 0) + 1

        sorted_words = sorted(freq.keys(), key=lambda k: (-freq[k], -len(k)))
        return sorted_words[:max_keywords]
