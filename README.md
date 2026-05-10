# 🌾 Urban Rural Connector (URC) - Gram-to-City
**A Unified Social Enterprise Ecosystem bridging the gap between rural producers and urban consumers through Smart Logistics and AI.**


## 🚀 Project Overview
URC is a first-year B.Tech CSE project designed to solve the "Middleman Crisis" in India. This platform establishes a high-trust digital link that ensures farmers receive fair market value for their produce while providing urban consumers with fresher goods at significantly lower costs. URC is more than just a storefront; it is a complete, technology-driven ecosystem.


## ✨ Key Features & Innovations
* **🚜 One Unified Website, Two Powerful Modules:** Although the platform operates as a single seamless website, it is powered by two interconnected backend modules (Marketplace & Logistics) that sync in real-time to handle the entire lifecycle of an order.
* 
* **🤖 Persona-Adaptive AI Assistant:** A sophisticated chatbot powered by **Groq (Llama-3.3-70B)**. It automatically detects which part of the website you are on to change its persona—acting as a *Rural Aide* for farmers, an *Urban Assistant* for shoppers, or a *Logistics Expert* for delivery drivers.
* 
* **🔐 Dual-Handshake Security Protocol:** A robust, two-stage **Dual-OTP system** ensures end-to-end security. A "Pickup OTP" confirms the driver has the goods from the farm, and a "Delivery OTP" ensures the buyer has received the package before payment is released.
* **👥 Community-Driven Economy:** Integrated **Group Pooling** technology allows urban neighbors to join orders together, automatically triggering shared delivery routes and reducing individual shipping costs by 20%.
* 
* **🚛 Eco-Friendly "Reverse Logistics":** To maximize efficiency, the platform utilizes **Back-haul Optimization**, allowing farmers to book space on returning delivery vehicles to bring city supplies back to villages at a 40% discount.


## 🛠️ Tech Stack
* **Backend:** Flask (Python)
* **Database:** Unified SQLite with SQLAlchemy (Shared across modules)
* **AI Engine:** Groq Cloud API (Llama-3.3-70B-Versatile)
* **Frontend:** Modern HTML5, CSS3 (Syne & IBM Plex Mono), and Vanilla JavaScript


## 📂 Project Architecture
The website is architected into two specialized modules that stay connected through a shared database:
* **Marketplace Module (`URC_Main_Website`)**: Manages the storefront, user profiles, AI personas, and the core shopping experience.
* **Logistics Hub (`URC_Transport_Module`)**: Powers the real-time tracking, GPS calculations, and the secure OTP verification engine.


## 📦 How to Run Locally
1. Clone the repository to your machine.
2. Install dependencies: `pip install -r requirements.txt`
3. Launch the platform:
   - **Terminal 1 (Marketplace)**: `cd URC_Main_Website && python app.py`
   - **Terminal 2 (Logistics)**: `cd URC_Transport_Module && python app.py`
   - Open your browser to `http://127.0.0.1:5000`.


## 👤 Author
**Drashti Parmar (Dasu)**<br>
1st Year B.Tech CSE Student @ Navrachana University<br>
Developing technology to create social impact and empower rural India.
