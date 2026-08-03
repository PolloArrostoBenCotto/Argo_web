# 🏛️ ARGOchive — Online archive of the ARGO project!

[![Live Demo](https://img.shields.io/badge/Demo-argoproject.vercel.app-orange?style=for-the-badge&logo=vercel)](https://argoproject.vercel.app/)
[![Stardance Ready](https://img.shields.io/badge/Submission-Stardance-blue?style=for-the-badge)](https://stardance.hackclub.com/projects/39048)

> *"Halve the time, double the results!"* > **ARGOchive** is the online archive made as a part of our robotics project for the **WRO2026** edition, to be presented in Zagabria in October.

---

## 📌 Overview

This is the web part of the project, allowing anyone that uses our robot to create 3d scans of the archeological artefacts to publish them on the world wide web, making it accessible to every archeologist in the world.

Designed and built by high school students passionate about robotics, mechanics, and software engineering, ARGO aims to bring innovation and accessibility to the world of archeology.

- 🌐 **Live Web Application:** [argoproject.vercel.app](https://argoproject.vercel.app/)
>the current demo doesn't allow for upload or download of the files, since the github repository can't be modified through it. Sorry for the inconvenience🙏.

---

## ✨ Key Features (of the full project)

- 🗄️ **Digital Artifact Archive:** Centralized database (`/archivio`) to store, search, and manage field discoveries.
- 🗿 **On-Site Archaeological Assistance:** Robot abilitated to assist archeologists directly in the trench, optimized for rough terrain.
- 📦 **Storage space for long Excavations** Argo is equipped with a conveyor belt fully expandable to fit any specific needs required for different sites.
- 🧊 **3D Point Cloud Processing & Rendering:** The scanner module on the robot is capable of creating full high-resolution 3d scans of each repert, outputting a complete and tidy folder.
- 📑 **Comprehensive Documentation:** Full technical blueprints, hardware designs, and software specs available directly within the site. Currently only the version 1.0 blueprints are avaliable, since the 2.0 are still to be completed.

---

## 🛠️ Architecture & Tech Stack

### Site
- **Frontend:** HTML5, CSS3, JavaScript (Deployed on **Vercel**)
- **Backend:** **FastAPI** (Python) for fast data throughput and point cloud manipulation

### Software
- **3D Rendering:** OPENMVG / OPENMVS, rmbg to clean the images
- **Rover control:** C++ and Python, using Arduino UNO, RaspberryPi and ESPs.

### Hardware & System Integration
- **Sensors:** Laser sensors, Infrared to avoid collision and UWB to follow remote holder.
- **Scanners:** Well lit PiCameras.

---

### VERSION LOG
- 1.0 - archive only, newfile over archive
- 1.1 - archive only, side by side
- 1.2 - homepage, archive and newfile side by side
- 1.3 - newfile and new folder in separate pages, new research missing
- 1.4 - full functionality, only home and archive
- 1.5 - team and support pages, different body font
- 1.6 - search and details, web deployment
