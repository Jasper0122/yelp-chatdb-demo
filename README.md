# 🍽️ Yelp ChatDB — Natural Language Restaurant Search System (DSCI 510)

**Author:** Zongrong Li  
**Course:** DSCI 510 ChatDB 82  
**Project:** Restaurant Chat Assistant with GPT, MongoDB, and Yelp API  

---

## 📌 Project Description

Yelp ChatDB is a full-stack chatbot application that enables users to search for restaurants and manage personal wishlists using **natural language queries**. The backend leverages GPT for intent parsing, MongoDB for caching and data storage, and the Yelp Fusion API for real-time restaurant data. The frontend is a lightweight React-like interface that supports conversational search.

---

## ⚙️ Prerequisites

Before running the project, make sure the following are installed:

- Python 3.8+
- Node.js (for frontend, optional)
- MongoDB (locally or Atlas)
- [Yelp Fusion API Key](https://www.yelp.com/developers/v3/manage_app)
- [OpenAI API Key](https://platform.openai.com/account/api-keys)

---

## 📁 Directory Structure

```
yelp-chatdb-demo/
├── app/
│   ├── main.py          # FastAPI backend
│   ├── db.py            # MongoDB connection
│   ├── nlp.py           # GPT parsing
│   ├── yelp.py          # Yelp data fetching
│   └── config.py        # API key loader
├── frontend/            # HTML/JS UI (optional)
├── .env                 # Store your API keys here
├── requirements.txt
└── README.md
```

---

## 🔑 API Key Setup

Create a `.env` file at the root of the project (if not already present):

```
OPENAI_API_KEY=your-openai-key-here
YELP_API_KEY=your-yelp-key-here
```

These keys are loaded via `config.py` using `python-dotenv`.

---

## 📦 Installation & Setup

1. **Clone the Repository**

```bash
git clone https://github.com/Jasper0122/yelp-chatdb-demo
cd yelp-chatdb-demo
```

2. **Create a Virtual Environment**

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate         # Windows
```

3. **Install Dependencies**

```bash
pip install -r requirements.txt
```

4. **Start MongoDB**

Ensure MongoDB is running locally at `mongodb://localhost:27017`.

5. **Launch Backend**

```bash
uvicorn app.main:app --reload
```

6. **Access Frontend**

Open your browser and go to:  
```
http://127.0.0.1:8000
```

---

## 💬 Example Queries

Try these natural language queries in the chat UI:

- `Find Thai restaurants in New York`
- `Show me 5-star sushi in Los Angeles`
- `Add Shake Shack to my wishlist`
- `Remove Shake Shack from my wishlist`
- `Show wishlist with restaurant info`
- `View my chat history`

---

## 🛠️ Tech Stack

- **Backend:** FastAPI, Pydantic, Uvicorn
- **NLP:** OpenAI GPT via API
- **Database:** MongoDB with custom schema
- **Frontend:** Static HTML + JavaScript
- **Data Source:** Yelp Fusion API

---

## ✅ Features

- ✅ Natural language restaurant search
- ✅ GPT-powered intent parsing
- ✅ Local MongoDB caching to reduce Yelp API calls
- ✅ Wishlist add/remove with notes
- ✅ Chat history viewing
- ✅ Support for API key security via .env

---

## 📂 Exported Data (Optional)

Run the following script to export current database contents into JSON files:

```bash
python dump_collections.py
```

This generates:

- `restaurants.json`
- `wishlists.json`
- `conversations.json`

---

## ❓Troubleshooting

- Make sure `.env` file is present and contains valid keys.
- Check MongoDB service is running on `localhost`.
- If GPT fails, confirm your OpenAI API quota and key.
- For UI not loading, confirm CORS is allowed or access from same origin.

---

## 📬 Contact

For questions or issues, email: [zongrong@usc.edu]