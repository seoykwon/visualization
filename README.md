# 🗺️ Visualization of Seoul Accessibility Map
‼️ DO NOT DIRECTLY MERGE / COMMIT TO THE MAIN BRANCH ‼️  

### **Find the position**  
1. ```cd Desktop```
2. ```cd visualization```
3. ```code .```
   
### **Setup**  
1. **BACKEND** (macOS / Linux)
      - navigate yourself to appropriate directory. ```cd backend```  
      - make your python virtual environment. if you already have one, you can skip this step. ```python3 -m venv venv```  
      - activate your virtual environment. ```source venv/bin/activate```  
      - download all the required dependencies. ```pip install -r requirements.txt```
      - run your server. ```python3 app.py```  

2. **FRONTEND** (macOS / Linux)
      - navigate ```cd frontend```
      - install required dependencies. ```npm install```
      - run your UI/UX. ```npm start```  

3. **CREATE YOUR BRANCH**
      - ```git checkout main```  
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
