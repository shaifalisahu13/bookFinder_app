import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import numpy as np
import time

# Streamlit UI Configuration
st.set_page_config(page_title="Book Price Finder Pro", layout="wide")
st.title("📖 Smart Book Price Finder")

# --- Available websites for scraping ---
WEBSITE_OPTIONS = [
    "https://www.amazon.in/",
    # add more e‑commerce sites here in the future
]

# Input Section
with st.form("search_form"):
    col1, col2 = st.columns(2)
    with col1:
        book_name = st.text_input(
            "Book Name*", 
            placeholder="Enter book name", 
            help="Required field"
        )
    with col2:
        language = st.text_input(
            "Language", 
            placeholder="Any language", 
            help="Optional field"
        )
    # ← now a dropdown instead of free‑text
    website = st.selectbox(
        "Website", 
        options=WEBSITE_OPTIONS, 
        index=0,
        help="Select which site to scrape"
    )
    search_button = st.form_submit_button("🔍 Search Books")

def scrape_books(website, book_name, language):
    """Scrape book data from specified website"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    service = Service(r"C:\Windows\chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        driver.get(website)
        
        # Handle category selection
        try:
            dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "searchDropdownBox"))
            )
            Select(dropdown).select_by_visible_text("Books")
        except:
            pass

        # Perform search
        search_query = f"{book_name} {language}".strip() if language else book_name
        try:
            searchbar = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
            )
            searchbar.send_keys(search_query, Keys.RETURN)
        except Exception as e:
            st.error(f"Search failed: {e}")
            return pd.DataFrame()

        # Sort results
        try:
            sorting = Select(WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "s-result-sort-select"))
            ))
            sorting.select_by_value("review-rank")
            time.sleep(2)
        except:
            pass

        books_data = []

        def extract_book_info(item):
            """Extract individual book details"""
            try:
                title = item.find_element(By.CSS_SELECTOR, "h2 span").text
            except:
                title = pd.NA
            
            try:
                # Try finding author by various selectors
                author_block = item.find_element(By.XPATH, ".//div[starts-with(@class, 'a-row') and contains(., 'by')]")
                author_elements = author_block.find_elements(By.XPATH, ".//a | .//span")
                authors = [el.text for el in author_elements if el.text.strip() and el.text.lower() != 'by']
                author = ", ".join(authors) if authors else pd.NA
            except:
                author = pd.NA
            
            try:
                price = item.find_element(
                    By.CSS_SELECTOR, ".a-price .a-offscreen"
                ).get_attribute("textContent")
            except:
                price = pd.NA
            
            try:
                link = item.find_element(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline").get_attribute("href")
            except:
                link = pd.NA
            return {"Title": title, "Author": author, "Price": price,"Link": link}

        # Pagination handling (limit 3 pages / 30 results)
        page = 1
        while page <= 3:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "[data-component-type='s-search-result']")
                    )
                )
                items = driver.find_elements(
                    By.CSS_SELECTOR, "[data-component-type='s-search-result']"
                )
                for item in items:
                    books_data.append(extract_book_info(item))
                if len(books_data) >= 30:
                    break
                next_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, ".s-pagination-next:not(.s-pagination-disabled)")
                    )
                )
                next_btn.click()
                page += 1
                time.sleep(2)
            except:
                break

        return pd.DataFrame(books_data)

    finally:
        driver.quit()

if search_button:
    if not book_name.strip():
        st.error("❌ Please enter a book name")
        st.stop()
    
    with st.spinner(f"Searching for '{book_name}' on {website}…"):
        try:
            df = scrape_books(website, book_name, language)
            
            if not df.empty:
                # Add searched book name column
                df['Searched Book'] = book_name
                
                # Clean and process data
                df['Price'] = (
                    df['Price']
                    .str.replace('[₹,]', '', regex=True)
                    .replace('', pd.NA)
                    .pipe(pd.to_numeric, errors='coerce')
                )
                
                df = df.dropna(subset=['Price']).reset_index(drop=True)
                
                if not df.empty:
                    
                    
                    # Sort by price (numeric)
                    df = df.sort_values(by='Price').reset_index(drop=True)
                    
                    # Save numeric price column separately for stats
                    df['NumericPrice'] = df['Price']

                    # Filter out ₹0.00 or free items
                    non_zero_df = df[df['NumericPrice'] > 0]
                    
                    # Create formatted ₹ price
                    df['Price'] = df['NumericPrice'].apply(lambda x: f'₹{x:,.2f}')
                    
                    # Create clickable hyperlinks in HTML
                    df['Hyperlink'] = df['Link'].apply(lambda x: f'<a href="{x}" target="_blank">Click Here</a>' if pd.notna(x) else '')

                    

                    # Display results
                    st.success(f"🎉 Found {len(df)} valid entries for '{book_name}'")
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.subheader("All Results")
                        st.write(
                        df[['Searched Book', 'Title', 'Author', 'Price', 'Hyperlink']]
                        .to_html(escape=False, index=False), 
                        unsafe_allow_html=True 
                        
                    )
                    csv = df[['Searched Book', 'Title', 'Author', 'Price', 'Link']].to_csv(index=False)
                    st.download_button(
                        label="📥 Download as CSV",
                        data=csv,
                        file_name=f"{book_name.replace(' ', '_')}_book_prices.csv",
                        mime="text/csv"
                    )
                    
                    with col2:
                        st.subheader("💰 Top 3 Cheapest")
                        top3 = df.head(3).reset_index(drop=True)
                        # Only show Title and Price
                        top3_display = top3[['Title', 'Price']].copy()

                        # Make Title clickable
                        top3_display['Title'] = top3['Link'].apply(
                            lambda x: f'<a href="{x}" target="_blank">{top3["Title"][top3["Link"] == x].values[0]}</a>'
                            if pd.notna(x) else top3["Title"][top3["Link"] == x].values[0]
                        )
                        st.write(top3_display.to_html(escape=False, index=False), unsafe_allow_html=True)
                        non_zero_df = df[df['NumericPrice'] > 0]
                        
                        
                        # Statistics
                        if not non_zero_df.empty:
                            lowest = non_zero_df['NumericPrice'].min()
                            avg_price = non_zero_df['NumericPrice'].mean()

                            st.metric("Lowest Price", f"₹{lowest:,.2f}")
                            st.metric("Average Price", f"₹{avg_price:,.2f}")
                        else:
                            st.warning("⚠️ All prices are ₹0.00 or unavailable. Cannot calculate lowest/average.")
                                                
                            
                            lowest = top3['Price'].iloc[0]
                            avg_price = (
                                df['Price']
                                .str.replace('₹','')
                                .str.replace(',','')
                                .astype(float)
                                .mean()
                            )
                            st.metric("Lowest Price", lowest)
                            st.metric("Average Price", f"₹{avg_price:,.2f}")
                else:
                    st.warning("⚠️ No valid prices found after cleaning")
            else:
                st.warning("⚠️ No books found matching your search")

        except Exception as e:
            st.error(f"🚨 Error occurred: {e}")
            st.exception(e)