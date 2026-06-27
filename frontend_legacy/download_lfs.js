/**
 * Node Vercel LFS Resolver
 * Vercel breaks native git-lfs because it uses shallow clones and strips the `.git/config`.
 * This script manually finds Git LFS text pointers in the public directory and 
 * downloads the actual binary files directly from GitHub's raw media CDN.
 */
const fs = require('fs');
const path = require('path');
const https = require('https');

const REPO = "Akhil-0412/FormulAI";
const BRANCH = "main";
const ASSETS_DIR = path.join(__dirname, 'public', 'assets');

function downloadFile(url, dest) {
    return new Promise((resolve, reject) => {
        const file = fs.createWriteStream(dest);
        https.get(url, (response) => {
            if (response.statusCode === 301 || response.statusCode === 302) {
                return downloadFile(response.headers.location, dest).then(resolve).catch(reject);
            }
            if (response.statusCode !== 200) {
                reject(new Error(`Failed to get '${url}' (${response.statusCode})`));
                return;
            }
            response.pipe(file);
            file.on('finish', () => {
                file.close(resolve);
            });
        }).on('error', (err) => {
            fs.unlink(dest, () => reject(err));
        });
    });
}

async function processDirectory(dir) {
    const files = fs.readdirSync(dir);
    for (const file of files) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
            await processDirectory(fullPath);
        } else if (stat.size < 500) { // LFS pointers are tiny (~130 bytes)
            const content = fs.readFileSync(fullPath, 'utf8');
            if (content.startsWith('version https://git-lfs.github.com/spec/v1')) {
                // It's a pointer! Download the real file
                const relativePath = path.relative(__dirname, fullPath).replace(/\\/g, '/');
                // GitHub LFS Raw Media URL
                const url = `https://media.githubusercontent.com/media/${REPO}/${BRANCH}/frontend/${relativePath}`;
                console.log(`[LFS Downloader] Resolving ${relativePath} ...\n -> ${url}`);
                try {
                    await downloadFile(url, fullPath);
                    console.log(`[LFS Downloader] Successfully downloaded ${file}`);
                } catch (err) {
                    console.error(`[LFS Downloader] Failed to download ${file}:`, err.message);
                }
            }
        }
    }
}

async function main() {
    console.log("[LFS Downloader] Starting Vercel LFS asset hydration...");
    if (fs.existsSync(ASSETS_DIR)) {
        await processDirectory(ASSETS_DIR);
    } else {
        console.log("[LFS Downloader] Assets directory not found:", ASSETS_DIR);
    }
}

main();
