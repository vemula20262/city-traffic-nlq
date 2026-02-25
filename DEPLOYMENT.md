# Deployment Guide: Atlas + Render + Vercel

Your database is seeded and ready! Follow these steps to deploy:

## ✅ Step 1: Database (COMPLETED)
- Database: `city_traffic_nlq`
- Collection: `crashes`
- Records: 3 sample NYC crash records with embeddings & geohashing
- URI: `mongodb+srv://tvemula3_db_user:Thushar%401@cluster.mgnnzud.mongodb.net/city_traffic_nlq?retryWrites=true&w=majority`

---

## 📦 Step 2: Deploy Backend to Render

### 2a. Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up (free tier is fine)
3. Connect your GitHub account

### 2b. Deploy from Git
1. Dashboard → **New** → **Web Service**
2. Connect your GitHub repo: `city-traffic-nlq`
3. Settings:
   - **Name:** `city-traffic-nlq-api`
   - **Environment:** `Python 3.10`
   - **Root Directory:** `showcase/backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT app:app`
   - **Plan:** Free

### 2c. Add Environment Variables
In Render dashboard, go to **Environment**:
```
MONGO_URI=mongodb+srv://tvemula3_db_user:Thushar%401@cluster.mgnnzud.mongodb.net/city_traffic_nlq?retryWrites=true&w=majority
MONGO_DB=city_traffic_nlq
MONGO_COLLECTION=crashes
PORT=5000
```

4. Click **Deploy**
5. Wait ~2-3 minutes for build to complete
6. You'll get a URL like: `https://city-traffic-nlq-api.render.com`

---

## 🎨 Step 3: Deploy Frontend to Vercel

### 3a. Create Vercel Account
1. Go to [vercel.com](https://vercel.com)
2. Sign up with GitHub
3. Go to **Dashboard**

### 3b. Import and Deploy
1. Click **Add New** → **Project**
2. Select **Import Git Repository**
3. Enter: `https://github.com/vemula20262/city-traffic-nlq`
4. **Root Directory:** `showcase/frontend`
5. **Build Settings:**
   - Framework: `Vite`
   - Build Command: `npm run build`
   - Output Directory: `dist`

### 3c. Environment Variables
Add in **Project Settings** → **Environment Variables**:
```
VITE_API_URL=https://city-traffic-nlq-api.render.com
```
(Replace with your actual Render backend URL from step 2)

6. Click **Deploy**
7. Wait for build to complete (~1-2 minutes)
8. You'll get a URL like: `https://city-traffic-nlq.vercel.app`

---

## 🔗 Step 4: Final Setup

Once both are deployed:

1. **Test Backend API:**
   ```
   curl https://city-traffic-nlq-api.render.com/health
   ```

2. **Visit Frontend:**
   ```
   https://city-traffic-nlq.vercel.app
   ```

3. **Try a Natural Language Query:**
   - "Show crashes in Manhattan with injuries"
   - "Find collisions near Times Square"
   - "Pedestrian accidents in Brooklyn last month"

---

## 📝 Notes

- First deployment may take 2-3 minutes as Render/Vercel install dependencies
- Your backend has 3 sample crash records to test with
- Frontend connects to backend via `VITE_API_URL` environment variable
- All data is in MongoDB Atlas, fully secure with IP whitelist

---

## 🆘 Troubleshooting

**Backend won't deploy?**
- Check render.yaml is committed and pushed
- Verify MONGO_URI environment variable is set correctly
- Check Render build logs for errors

**Frontend API calls failing?**
- Ensure VITE_API_URL points to correct Render backend URL
- Check browser console for CORS issues
- Verify backend is running (test health endpoint)

**Can't connect to Atlas?**
- Add your IP to MongoDB Atlas IP whitelist (Security → Network Access)
- Verify database name is `city_traffic_nlq` (not lowercase)
- Check password encoding (@ → %40)
