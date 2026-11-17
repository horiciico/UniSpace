# CONTEXT — UniSpace vocabulary

<!-- graffino-agentic:begin v1 -->
> The approved terms for this project. Use each term exactly as defined, in the part
> of speech given. Never swap in a synonym; never use a word on an _Avoid_ line.
<!-- graffino-agentic:end -->

**UniSpace** (noun) — the web platform this repository builds.
_Avoid_: "the app" when you mean the whole platform

**Backend** (noun) — the FastAPI service in `backend/`, which serves the API and talks to the database.
_Avoid_: "server", "API" when you mean the whole service

**Frontend** (noun) — the static HTML, CSS and JS in `frontend/`, served by nginx.
_Avoid_: "client", "UI" when you mean the code files

**Migration** (noun) — an Alembic revision in `backend/alembic/versions/` that changes the database schema.
_Avoid_: "schema change" when you mean the file itself

# Project brief (Romanian, verbatim from the course description)

## Orar + rezervare săli pentru facultatea ta
Categoria C · Universitate · Dificultate ★★★★ · Efort estimat ~38h · Runda 1 · 1 student
Pe scurt: importi orarul real al facultății, îl faci navigabil pe grupe / profesori / săli, găsești săli libere acum și permiți rezervarea lor pentru activități studențești, cu reguli de prioritate.

### 🧑 Input uman obligatoriu
Orarul real al facultății tale pentru semestrul curent (PDF, Excel, pagină web — îl parsezi tu). Inventar de teren pentru minim 12 săli: capacitate reală (numeri scaunele), proiector, table, prize, cum se deschide. Vorbești cu secretariatul sau cu un responsabil de orar despre cum se aprobă o rezervare și cu un lider de organizație studențească despre cum își găsesc săli acum. FIELD.md + INTERVIEW.md.

### Context real
Orarul e un PDF pe site. Nimeni nu știe ce sală e liberă marți la 16. Organizațiile studențești trimit email-uri la secretariat și așteaptă. Semestrul are săptămâni pare / impare, vacanțe, sesiune, iar un curs mutat o singură dată strică orice regulă.

### Cerințe funcționale (must)
- Import al orarului real într-un model normalizat: activitate (curs / seminar / lab), disciplină, cadru didactic, grupă / serie, sală, zi, interval, săptămâni (pară / impară / toate / listă explicită).
- Vizualizări: pe grupă, pe profesor, pe sală; săptămâna curentă cu paritatea corectă; export iCal cu URL de abonare per grupă.
- "Săli libere acum" și "săli libere în intervalul X", cu filtre (capacitate ≥ N, proiector).
- Rezervare de sală pentru activități studențești: cerere → aprobare de către un admin → confirmare; conflicte detectate la cerere.
- Modificări de orar (un curs mutat într-o săptămână anume) cu istoric și notificare către grupa abonată.
- Anunțuri pe disciplină / grupă (curs anulat, sală schimbată) vizibile în orar și trimise pe email.
- Structura semestrului configurabilă: prima săptămână, vacanțe, sesiune, săptămâni cu paritate inversată (dacă e cazul).
- Roluri: student, cadru didactic (își vede orarul și poate anunța), organizație studențească (rezervă), admin.

### Cerințe tehnice specifice
- Evenimentele recurente se stochează ca regulă + excepții (nu 14 rânduri copiate); expansiunea pe o săptămână e testată.
- iCal generat corect (timezone, RRULE sau instanțe explicite, UID stabile); verificat prin import în Google Calendar / Apple Calendar.
- Parserul orarului e un script reproductibil în repo, cu raport de linii neinterpretate.
- Detecția conflictelor e o funcție pură, testată pe suprapuneri parțiale și pe parități diferite.

### 🌀 Twist: priorități și "bump"
Rezervările au priorități: curs > examen > activitate oficială a facultății > organizație studențească > student. O activitate cu prioritate mai mare poate "bumpui" o rezervare existentă, dar: rezervarea bumpuită primește notificare, o propunere automată de sală alternativă echivalentă (capacitate și dotări ≥ cele cerute, cât mai aproape în timp) și un termen de răspuns; dacă nu răspunde, se mută automat. Paritatea săptămânilor, vacanțele și o săptămână "inversată" trebuie să fie corecte în tot acest lanț. Regulile exacte le validezi cu secretariatul.

### Variabilele tale
- Facultatea, semestrul și cele 12 săli inventariate.
- Structura reală a semestrului (prima săptămână, vacanțe, sesiune).
- Lanțul de priorități și termenul de răspuns la bump, validate cu secretariatul.

### ✅ Definition of Done
- Orarul real e pe live; o grupă reală își vede săptămâna curentă corect (verificat cu 2 colegi).
- "Săli libere acum" e corect pentru cele 12 săli inventariate.
- Bump-ul cu propunere alternativă funcționează, cu teste pe priorități.
- iCal-ul se importă fără erori în Google Calendar.
- Raportul parserului arată ce linii din orar nu au putut fi interpretate.
