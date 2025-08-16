# 🗺️ Visualization of Seoul Accessibility Map
‼️ DO NOT DIRECTLY MERGE / COMMIT TO THE MAIN BRANCH ‼️  

### **Find the position**  
1. ```cd Desktop```
2. ```cd visualization```
3. ```code .```
   
### ⊆ **Setup**  
1. **BACKEND** (macOS / Linux)
      - navigate yourself to appropriate directory. ```cd backend```  
      - [🌟 only once] make your python virtual environment. if you already have one, you can skip this step. ```python3 -m venv venv```  
      - activate your virtual environment. ```source venv/bin/activate```  
      - [🌟 only once] download all the required dependencies. ```pip install -r requirements.txt```
      - run your server. ```python3 app.py```  

2. **FRONTEND** (macOS / Linux)
      - navigate ```cd frontend```
      - [🌟 only once] install required dependencies. ```npm install```
      - run your UI/UX. ```npm start```  

3. **CREATE YOUR BRANCH**
      - ```git main```  
      - ```git pull origin main``` / ```git pull```
      - ```git checkout -b feature-name```
      - ```git push -u origin feature-name```
  
4. **ADD/COMMIT YOUR CODE**
      - ```git add .```
      - ```git commit -m "commit messages"```

5. **SEND MERGE REQUEST**
      - go to your repository page
      - "compare & pull request"
      - base branch: ```main```
      - compare branch: ```my-branch-name```
      - fill in title + description, click **Create pull request**  

### 🌳 **Source Tree**  
1. **Clone or add your existing repo**
      - click clone
      - paste your repo's HTTPS or SSH URL

2. **Workflow in Sourcetree**
      - **Fetch** -> update remote branch list
      - **Checkout** -> switch to branch
      - **Commit** -> stage changes & commit
      - **Push** -> send branch to remote
      - **Create pull / Merge request** -> right-click branch -> "create pull request"  
