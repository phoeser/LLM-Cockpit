# -*- coding: utf-8 -*-
"""
Crawl ERGO Berater homepages and discover internal links.

Reads berater_data.json, crawls each berater's homepage and discovers subpages
up to 1 level deep, then outputs a JSON sitemap and an interactive HTML visualization.

Usage:
    python scripts/crawl_berater_sitemap.py
    BERATER_SITEMAP_LIMIT=50 python scripts/crawl_berater_sitemap.py
"""

import json
import sys
import os
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from pathlib import Path
import base64

# Configuration
MAX_THREADS = 5
DELAY_PER_THREAD = 0.3  # seconds between requests per thread
REQUEST_TIMEOUT = 10  # seconds
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
DEFAULT_LIMIT = 200
LIMIT = int(os.environ.get('BERATER_SITEMAP_LIMIT', DEFAULT_LIMIT))


class LinkExtractor(HTMLParser):
    """Extract links from HTML content."""

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = set()
        self.title = ""
        self.title_found = False

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href' and value:
                    # Normalize and add link
                    link = urljoin(self.base_url, value)
                    # Remove fragments
                    link = link.split('#')[0]
                    self.links.add(link)
        elif tag == 'title' and not self.title_found:
            self.title_found = True

    def handle_data(self, data):
        if self.title_found and not self.title:
            self.title = data.strip()
            self.title_found = False


def get_domain(url):
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc


def is_internal_link(link, homepage):
    """Check if link is internal (same domain)."""
    link_domain = get_domain(link)
    home_domain = get_domain(homepage)
    return link_domain == home_domain


def fetch_page(url, timeout=REQUEST_TIMEOUT):
    """Fetch a page and return (status_code, content, title)."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode('utf-8', errors='ignore')
            return (response.status, content, url)
    except urllib.error.HTTPError as e:
        return (e.code, None, url)
    except urllib.error.URLError:
        return (None, None, url)
    except Exception:
        return (None, None, url)


def extract_title(html_content):
    """Extract title from HTML."""
    parser = LinkExtractor("http://dummy.com")
    try:
        parser.feed(html_content)
        return parser.title if parser.title else ""
    except Exception:
        return ""


def crawl_homepage(berater_entry):
    """Crawl a berater's homepage and discover internal links."""
    homepage = berater_entry.get('homepage', '').strip()
    if not homepage or not homepage.endswith('.ergo.de'):
        return None

    # Add protocol
    home_url = f"https://{homepage}/" if not homepage.startswith('http') else homepage

    result = {
        'name': f"{berater_entry.get('firstname', '')} {berater_entry.get('lastname', '')}".strip(),
        'homepage': homepage,
        'city': berater_entry.get('city', ''),
        'zipcode': berater_entry.get('zipcode', ''),
        'pages': [],
        'page_count': 0,
        'status': 'error'
    }

    # Fetch homepage
    time.sleep(DELAY_PER_THREAD)
    status, content, _ = fetch_page(home_url)

    if status != 200 or not content:
        result['status'] = 'failed'
        return result

    # Extract homepage title and links
    parser = LinkExtractor(home_url)
    try:
        parser.feed(content)
    except Exception:
        parser.links = set()

    title = extract_title(content) or "Homepage"
    result['pages'].append({
        'url': home_url,
        'title': title
    })

    # Filter internal links
    internal_links = set()
    for link in parser.links:
        if is_internal_link(link, home_url) and link != home_url:
            # Normalize to avoid duplicates (remove trailing slashes for comparison)
            normalized = link.rstrip('/')
            internal_links.add(normalized)

    # Crawl internal links (1 level deep)
    for link in sorted(list(internal_links))[:50]:  # Limit to 50 subpages per berater
        time.sleep(DELAY_PER_THREAD)
        status, content, _ = fetch_page(link)

        if status == 200 and content:
            title = extract_title(content) or urlparse(link).path.strip('/') or "Untitled"
            result['pages'].append({
                'url': link,
                'title': title
            })

    result['page_count'] = len(result['pages'])
    result['status'] = 'ok' if result['page_count'] > 0 else 'empty'
    return result


def calculate_summary(berater_list):
    """Calculate summary statistics."""
    if not berater_list:
        return {
            'avg_pages': 0,
            'max_pages': 0,
            'min_pages': 0,
            'total_unique_urls': 0,
            'common_subpages': {}
        }

    page_counts = [b['page_count'] for b in berater_list if b['page_count'] > 0]
    all_urls = []
    subpage_paths = {}

    for berater in berater_list:
        for page in berater['pages']:
            all_urls.append(page['url'])
            # Extract path for common subpage analysis
            path = urlparse(page['url']).path.strip('/')
            if path:
                subpage_paths[path] = subpage_paths.get(path, 0) + 1

    # Sort subpages by frequency
    top_subpages = dict(sorted(subpage_paths.items(), key=lambda x: x[1], reverse=True)[:20])

    return {
        'avg_pages': round(sum(page_counts) / len(page_counts), 1) if page_counts else 0,
        'max_pages': max(page_counts) if page_counts else 0,
        'min_pages': min(page_counts) if page_counts else 0,
        'total_unique_urls': len(set(all_urls)),
        'common_subpages': top_subpages
    }


def main():
    """Main function."""
    script_dir = Path(__file__).parent.parent
    berater_file = script_dir / 'berater_data.json'
    output_dir = script_dir / 'data'
    sitemap_dir = script_dir / 'sitemaps'

    # Create output directories
    output_dir.mkdir(exist_ok=True)
    sitemap_dir.mkdir(exist_ok=True)

    # Load berater data
    print(f"[*] Loading berater data from {berater_file}...")
    try:
        with open(berater_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] Error loading berater data: {e}")
        sys.exit(1)

    vermittler = data.get('vermittler', [])
    print(f"[*] Found {len(vermittler)} berater")

    # Filter berater with .ergo.de domains
    ergo_berater = [
        b for b in vermittler
        if b.get('homepage', '').endswith('.ergo.de')
    ]
    print(f"[*] Found {len(ergo_berater)} berater with .ergo.de domains")

    # Apply limit
    to_crawl = ergo_berater[:LIMIT]
    print(f"[*] Will crawl {len(to_crawl)} berater (limit: {LIMIT})")

    # Concurrent crawling
    crawled_berater = []
    print(f"[*] Starting crawl with {MAX_THREADS} threads...")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(crawl_homepage, b): b for b in to_crawl}
        completed = 0

        for future in as_completed(futures):
            completed += 1
            result = future.result()
            if result:
                crawled_berater.append(result)
                status = result.get('status', 'error')
                pages = result.get('page_count', 0)
                print(f"[{completed}/{len(to_crawl)}] {result['name']}: {pages} pages [{status}]")

    # Calculate summary
    summary = calculate_summary(crawled_berater)

    # Prepare output
    output = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total_berater': len(vermittler),
        'crawled': len(crawled_berater),
        'total_urls': summary['total_unique_urls'],
        'berater': crawled_berater,
        'summary': summary
    }

    # Save JSON sitemap
    output_file = output_dir / 'berater_sitemap_data.json'
    print(f"\n[*] Saving sitemap data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"[+] Saved: {output_file}")

    # Generate HTML sitemap
    html_file = sitemap_dir / 'berater_sitemap.html'
    print(f"[*] Generating HTML sitemap to {html_file}...")
    html_content = generate_html_sitemap(output)
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"[+] Saved: {html_file}")

    # Summary
    print(f"\n[+] Crawl complete!")
    print(f"    Total berater crawled: {len(crawled_berater)}")
    print(f"    Total unique URLs: {summary['total_unique_urls']}")
    print(f"    Average pages per berater: {summary['avg_pages']}")
    print(f"    Max pages: {summary['max_pages']}")


def generate_html_sitemap(data):
    """Generate interactive HTML sitemap."""
    berater = data.get('berater', [])
    summary = data.get('summary', {})

    # Count by page range
    page_ranges = {
        '1': 0,
        '2-5': 0,
        '6-10': 0,
        '11-20': 0,
        '21+': 0
    }
    for b in berater:
        count = b.get('page_count', 0)
        if count == 1:
            page_ranges['1'] += 1
        elif count <= 5:
            page_ranges['2-5'] += 1
        elif count <= 10:
            page_ranges['6-10'] += 1
        elif count <= 20:
            page_ranges['11-20'] += 1
        else:
            page_ranges['21+'] += 1

    # Top subpages
    common_subpages = summary.get('common_subpages', {})
    top_subpages_html = ''.join([
        f'<li>{path}: <strong>{count}</strong> berater</li>'
        for path, count in list(common_subpages.items())[:15]
    ])

    berater_json = json.dumps(berater)
    page_ranges_json = json.dumps(page_ranges)

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ERGO Berater – Sitemap-Visualisierung</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js" integrity="sha384-iU8HYtnGQ8Cy4zl7gbNMOhsDTTKX02BTXptVP/vqAWIaTfM7isw76iyZCsjL2eVi" crossorigin="anonymous"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            color: #ffffff;
            margin-bottom: 10px;
            font-size: 28px;
        }}
        .subtitle {{
            color: #888;
            margin-bottom: 30px;
            font-size: 14px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
        }}
        .stat-label {{
            color: #888;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .stat-value {{
            color: #fff;
            font-size: 28px;
            font-weight: bold;
        }}
        .charts-section {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }}
        .chart-container {{
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
        }}
        .chart-container h3 {{
            color: #fff;
            margin-bottom: 15px;
            font-size: 16px;
        }}
        .list-section {{
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }}
        .list-section h2 {{
            color: #fff;
            margin-bottom: 15px;
            font-size: 18px;
        }}
        .search-box {{
            margin-bottom: 20px;
        }}
        .search-box input {{
            width: 100%;
            padding: 12px;
            background: #0f0f0f;
            border: 1px solid #333;
            border-radius: 6px;
            color: #e0e0e0;
            font-size: 14px;
        }}
        .search-box input::placeholder {{
            color: #666;
        }}
        .berater-item {{
            background: #0f0f0f;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .berater-item:hover {{
            border-color: #555;
            background: #151515;
        }}
        .berater-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .berater-name {{
            font-weight: bold;
            color: #fff;
        }}
        .berater-meta {{
            color: #888;
            font-size: 12px;
            margin-top: 5px;
        }}
        .berater-pages {{
            display: inline-block;
            background: #333;
            color: #aaa;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .berater-urls {{
            display: none;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #333;
        }}
        .berater-urls.expanded {{
            display: block;
        }}
        .url-item {{
            color: #0a9eff;
            text-decoration: none;
            word-break: break-all;
            font-size: 12px;
            margin-bottom: 6px;
        }}
        .url-item:hover {{
            color: #1bb3ff;
            text-decoration: underline;
        }}
        .top-subpages {{
            background: #0f0f0f;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 20px;
        }}
        .top-subpages h3 {{
            color: #fff;
            margin-bottom: 15px;
        }}
        .top-subpages ul {{
            list-style: none;
        }}
        .top-subpages li {{
            color: #888;
            padding: 8px 0;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
        }}
        .top-subpages li:last-child {{
            border-bottom: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ERGO Berater – Sitemap-Visualisierung</h1>
        <div class="subtitle">Entdeckte Seiten und interne Verlinkungen</div>

        <div class="summary">
            <div class="stat-card">
                <div class="stat-label">Berater crawlt</div>
                <div class="stat-value">{data.get('crawled', 0)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Gesamte URLs</div>
                <div class="stat-value">{summary.get('total_unique_urls', 0)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Ø Seiten pro Berater</div>
                <div class="stat-value">{summary.get('avg_pages', 0)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Maximum Seiten</div>
                <div class="stat-value">{summary.get('max_pages', 0)}</div>
            </div>
        </div>

        <div class="charts-section">
            <div class="chart-container">
                <h3>Seitenanzahl-Verteilung</h3>
                <canvas id="pageDistributionChart"></canvas>
            </div>
            <div class="chart-container">
                <h3>Top Unterstützungsseiten</h3>
                <div class="top-subpages">
                    <ul>
                        {top_subpages_html}
                    </ul>
                </div>
            </div>
        </div>

        <div class="list-section">
            <h2>Berater durchsuchen</h2>
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Nach Name, Stadt oder Domain suchen...">
            </div>
            <div id="beraterList"></div>
        </div>
    </div>

    <script>
        const beraterData = {berater_json};
        const pageRanges = {page_ranges_json};

        // Page distribution chart
        const ctx = document.getElementById('pageDistributionChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: Object.keys(pageRanges),
                datasets: [{{
                    label: 'Anzahl Berater',
                    data: Object.values(pageRanges),
                    backgroundColor: '#0a9eff',
                    borderColor: '#0a9eff',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#888' }}
                    }}
                }},
                scales: {{
                    y: {{
                        ticks: {{ color: '#888' }},
                        grid: {{ color: '#333' }},
                        beginAtZero: true
                    }},
                    x: {{
                        ticks: {{ color: '#888' }},
                        grid: {{ color: '#333' }}
                    }}
                }}
            }}
        }});

        // Search and filter
        function renderBerater(filteredData) {{
            const container = document.getElementById('beraterList');
            container.innerHTML = '';

            filteredData.forEach(berater => {{
                const item = document.createElement('div');
                item.className = 'berater-item';

                const header = document.createElement('div');
                header.className = 'berater-header';
                header.innerHTML = `
                    <div>
                        <div class="berater-name">${{berater.name}}</div>
                        <div class="berater-meta">
                            <strong>${{berater.city}}</strong> •
                            <a href="https://${{berater.homepage}}/" target="_blank">${{berater.homepage}}</a>
                            <span class="berater-pages">${{berater.page_count}} Seiten</span>
                        </div>
                    </div>
                `;

                item.appendChild(header);

                const urls = document.createElement('div');
                urls.className = 'berater-urls';
                urls.innerHTML = berater.pages.map(p =>
                    `<div class="url-item"><a href="${{p.url}}" target="_blank">${{p.title}}</a></div>`
                ).join('');

                item.appendChild(urls);

                item.addEventListener('click', () => {{
                    urls.classList.toggle('expanded');
                }});

                container.appendChild(item);
            }});
        }}

        function filterBerater() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const filtered = beraterData.filter(b =>
                b.name.toLowerCase().includes(query) ||
                b.city.toLowerCase().includes(query) ||
                b.homepage.toLowerCase().includes(query)
            );
            renderBerater(filtered);
        }}

        document.getElementById('searchInput').addEventListener('input', filterBerater);

        // Initial render
        renderBerater(beraterData);
    </script>
</body>
</html>"""

    return html


if __name__ == '__main__':
    main()
