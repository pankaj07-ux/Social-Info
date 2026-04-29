# Social-Info 🌐

**TikTok and Instagram Profile Details API**

A Python-based API to fetch and retrieve detailed profile information from TikTok and Instagram social media platforms.

---

## 📋 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Requirements](#requirements)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## ✨ Features

- 🎬 **TikTok Profile Fetching** - Retrieve detailed TikTok user profiles
- 📸 **Instagram Profile Fetching** - Get comprehensive Instagram user information
- 🔍 **Profile Analytics** - Access follower counts, engagement metrics, and more
- ⚡ **Fast & Lightweight** - Optimized Python implementation
- 📊 **Structured Data** - Clean JSON responses for easy integration
- 🛡️ **Error Handling** - Robust error management and validation

---

## 🚀 Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### Steps

```bash
# Clone the repository
git clone https://github.com/pankaj07-ux/Social-Info.git

# Navigate to the project directory
cd Social-Info

# Install required dependencies
pip install -r requirements.txt
```

---

## 💻 Usage

### Basic Example

```python
from social_info import TikTok, Instagram

# TikTok Profile
tiktok = TikTok()
profile = tiktok.get_profile('username')
print(profile)

# Instagram Profile
instagram = Instagram()
profile = instagram.get_profile('username')
print(profile)
```

### Response Format

```json
{
  "username": "user123",
  "name": "Full Name",
  "followers": 10500,
  "following": 342,
  "posts": 156,
  "bio": "Bio description",
  "verified": true,
  "profile_url": "https://...",
  "avatar_url": "https://..."
}
```

---

## 📚 API Reference

### TikTok Module

#### `get_profile(username)`
Fetches TikTok profile details for a given username.

**Parameters:**
- `username` (str): TikTok username

**Returns:**
- Dictionary containing user profile data

---

### Instagram Module

#### `get_profile(username)`
Fetches Instagram profile details for a given username.

**Parameters:**
- `username` (str): Instagram username

**Returns:**
- Dictionary containing user profile data

---

## 📦 Requirements

```
requests>=2.28.0
beautifulsoup4>=4.11.0
```

See `requirements.txt` for more details.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 💬 Support

For support, questions, or issues:

- Create an [Issue](https://github.com/pankaj07-ux/Social-Info/issues)
- Contact: [pankaj07-ux](https://github.com/pankaj07-ux)

---

## ⭐ Show Your Support

If this project helped you, please consider giving it a star! ⭐

---

**Last Updated:** 2026-04-29