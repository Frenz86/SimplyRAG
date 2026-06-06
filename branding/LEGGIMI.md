# Branding / White-labeling OpenWebUI

Metti qui le tue immagini per sostituire logo e favicon di OpenWebUI.

## File da inserire (stessi nomi esatti)

| File | Cos'è | Dimensione consigliata | Formato |
|------|-------|------------------------|---------|
| `favicon.png` | Icona della tab del browser e logo piccolo | 512×512 px | PNG con trasparenza |
| `splash.png` | Schermata di caricamento (logo grande centrale) | 500×500 px | PNG con trasparenza |

> I nomi dei file **devono** essere esattamente `favicon.png` e `splash.png`.
> Se hai un solo logo quadrato, puoi usare lo stesso file per entrambi.

### Favicon della tab del browser

La tab del browser **non** usa `favicon.png`: carica `favicon.svg`, `favicon.ico`,
`favicon-96x96.png` e `apple-touch-icon.png` (Chrome preferisce l'SVG). Queste varianti
si **generano** automaticamente da `favicon.png`:

```
python branding/gen-favicons.py
```

Rilancialo ogni volta che cambi `favicon.png`. Lo script centra il logo (anche
rettangolare) su un canvas quadrato trasparente ed esporta tutte le varianti.

## Come attivarli

1. Metti `favicon.png` e `splash.png` in questa cartella.
2. Nel file `docker-compose.yml`, **decommenta** il blocco `# --- BRANDING ---`
   sotto i `volumes:` del servizio `open-webui`.
3. (Opzionale) Imposta il nome dell'app: nel compose, env `WEBUI_NAME: "Il Tuo Nome"`.
4. Ricrea il container:
   ```
   docker compose up -d open-webui
   ```

## ⚠️ Nota sui path (importante)

OpenWebUI cambia i percorsi dei file statici tra una versione e l'altra.
I mount nel compose sono tarati per la **v0.9.6**. Se aggiorni OpenWebUI e il
logo non cambia più, vanno riverificati i path dentro il container con:

```
docker exec open-webui sh -c "find /app -name 'favicon*' -o -name 'splash*'"
```
