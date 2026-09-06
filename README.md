# homecloud-drive
A self-hosted storage system designed to run on a home server and provide file storage and management to devices connected to the local network.

This repository contains the full-stack application component of the home storage system. It does not contain details on the Ubuntu configuration and the network topology.

## Running

Clone the repository. Install Docker Desktop for your OS, then navigate to codebase. 

```docker compose up -d --build```

Navigate to the frontend folder. Install NPM and Node.JS

Run:

```npm run dev```

Click the link that comes up in the terminal to interact with the frontend.

## Features

* User registration and authentication
* Session-token based authorisation
* Upload, download, view, and delete files
* Create and manage folders
* Per-user file permissions
* PostgreSQL storage for user and file metadata
* Trash system with 30-day file recovery
* Web-based client interface
* Designed for access over a local home network
* Headless Linux server accessible through SSH

## Architecture

The application is tested and deployed on a repurposed **Dell OptiPlex** running Ubuntu Server. Clients communicate with the FastAPI backend over the home network.

## Technologies Used

### Backend

* **Python**
* **FastAPI**: REST API and backend services
* **Psycopg**: PostgreSQL database interface
* **PostgreSQL**: user accounts and file metadata

### Frontend

* **Svelte**: web client and user interface

### Server / Systems Tools

* **Ubuntu Server**: home server operating system
* **OpenSSH**: remote server administration
* **Linux filesystem**: file storage

## Components 

The project consists of three main components:

* **Client**: Svelte/JS based interface for users to interact with their files.
* **Backend**: FastAPI application responsible for authentication, file management, permissions, and database communication.
* **Home Server**: Ubuntu Server machine hosting the application, PostgreSQL database, and stored files.