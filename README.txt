# 🏛️ ARGOchive — Argo Web Application

[![Live Demo](https://img.shields.io/badge/Demo-argoproject.vercel.app-blueviolet?style=for-the-badge&logo=vercel)](https://argoproject.vercel.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Stardance Ready](https://img.shields.io/badge/Submission-Stardance-blue?style=for-the-badge)]()

> *"Halve the time, double the results!"* > **ARGOchive** is an **Archeo-Helper** platform engineered to assist archaeological teams directly on-site by streamlining data acquisition, 3D point cloud processing, and artifact archiving.

---

## 📌 Overview

**ARGOchive (Argo Web)** is the web interface and software hub for the **ARGO** project. It connects field sensors, 3D laser scanners, and local processing units with a fast, modern web frontend and backend ecosystem. 

Designed and built by high school students passionate about robotics, mechanics, and software engineering, ARGOchive aims to bring innovative, accessible tools to historical and archaeological research.

- 🌐 **Live Web Application:** [argoproject.vercel.app](https://argoproject.vercel.app/)

---

## ✨ Key Features (of the full project)

- 🗿 **On-Site Archaeological Assistance:** Optimized for quick cataloging and analysis of even the smallest historical artifacts.
- 🧊 **3D Point Cloud Processing & Rendering:** Interactive visualization and local/cloud processing of scanned models.
- 🗄️ **Digital Artifact Archive:** Centralized database (`/archivio`) to store, search, and manage field discoveries.
- ⚙️ **High-Performance Backend:** Built with FastAPI for ultra-fast API response times and asynchronous processing.
- 📑 **Comprehensive Documentation:** Full technical blueprints, hardware designs, and software specs available directly within the app.

---

## 🛠️ Architecture & Tech Stack

### Software
- **Frontend:** HTML5, CSS3, JavaScript (Deployed on **Vercel**)
- **Backend:** **FastAPI** (Python) for fast data throughput and point cloud manipulation
- **3D Rendering:** WebGL / Point Cloud Rendering Libraries

### Hardware & System Integration
- **Sensors:** Environmental and spatial sensors for artifact context
- **Scanners:** 3D Laser Scanner integration
- **Processing Unit:** Local edge computing unit synced with the web platform

---

## 🚀 Getting Started

Follow these instructions to run the web application locally.

### Prerequisites

- **Node.js** (v16.x or later) / **Python** (v3.9+ for backend development)
- **Git**

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/PolloArrostoBenCotto/Argo_web.git](https://github.com/PolloArrostoBenCotto/Argo_web.git)
   cd Argo_web
   run startApp.bat and then ngrok.bat as admin, copy the link in the cmd window and past it in the url.

### VERSION LOG
1.0 - archive only, newfile over archive
1.1 - archive only, side by side
1.2 - homepage, archive and newfile side by side
1.3 - newfile and new folder in separate pages, new research missing
1.4 - full functionality, only home and archive
1.5 - team and support pages, different body font
1.6 - search and details, web deployment