import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import pandas as pd
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

def extract_lead_info(soup, base_url):
    text = soup.get_text()
    # Emails
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    emails = re.findall(email_pattern, text)
    
    # Phones
    phone_pattern = r'(\+?\d{1,3}?[\s.-]?)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}'
    phones = re.findall(phone_pattern, text)
    phone_numbers = ["".join(p) for p in phones if "".join(p).strip()]

    # Social Links
    social_links = []
    for link in soup.find_all("a", href=True):
        href = link['href']
        if any(social in href for social in ["linkedin.com", "facebook.com", "instagram.com", "twitter.com"]):
            social_links.append(href)

    # Meta Description
    meta = soup.find("meta", attrs={"name": "description"})
    description = meta["content"].strip() if meta and "content" in meta.attrs else ""

    # Website Title
    title = soup.title.string.strip() if soup.title else "Unknown Website"

    # Category Inference
    categories = {
        "realtor": "Real Estate",
        "fitness": "Fitness",
        "coach": "Coaching",
        "agency": "Agency",
        "clinic": "Health/Clinic",
        "law": "Law/Legal",
    }
    business_type = "General"
    for keyword, label in categories.items():
        if keyword in description.lower() or keyword in title.lower():
            business_type = label
            break

    return {
        "Website Name": title,
        "Description": description,
        "Emails": ", ".join(set(emails)) if emails else "No emails",
        "Phone Numbers": ", ".join(set(phone_numbers)) if phone_numbers else "No numbers",
        "Social Links": ", ".join(set(social_links)) if social_links else "None found",
        "Business Type": business_type
    }

def scrape_url_with_selenium(url):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument("--log-level=3")
    options.add_argument("--window-size=1920,1080")

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Try visiting contact page for more details
        contact_link = next(
            (urljoin(url, a['href']) for a in soup.find_all('a', href=True) if 'contact' in a['href'].lower()),
            None
        )

        # Crawl contact page too if available
        if contact_link:
            driver.get(contact_link)
            contact_soup = BeautifulSoup(driver.page_source, 'html.parser')
            full_soup = BeautifulSoup(str(soup) + str(contact_soup), 'html.parser')
        else:
            full_soup = soup

        lead_info = extract_lead_info(full_soup, url)
        driver.quit()

        return {
            "URL": url,
            **lead_info
        }

    except Exception as e:
        return {"URL": url, "Website Name": "Error", "Description": "-", "Emails": f"Error: {e}", "Phone Numbers": "-", "Social Links": "-", "Business Type": "-"}

# Streamlit UI
def main():
    st.set_page_config(page_title="Lead Generator Tool", layout="wide")
    st.title("📬 Lead Generator & Email Scraper")

    st.markdown("Paste a list of website URLs (one per line):")
    urls_text = st.text_area("Enter URLs", height=200, placeholder="https://example.com\nhttps://another.com")

    if st.button("Start Scraping Leads"):
        urls = [url.strip() for url in urls_text.splitlines() if url.strip()]
        if not urls:
            st.warning("Please enter at least one valid URL.")
            return

        with st.spinner("Scraping websites for lead data..."):
            with ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(scrape_url_with_selenium, urls))

        df = pd.DataFrame(results)
        st.success("✅ Lead scraping completed!")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Leads CSV", data=csv, file_name="leads_data.csv", mime="text/csv")

if __name__ == "__main__":
    main()
