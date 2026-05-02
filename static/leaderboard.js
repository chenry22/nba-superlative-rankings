let lastCursor = null;
let rankOffset = 0;

async function loadLeaderboard(category) {
    if (document.getElementsByClassName('active')[0]) {
        document.getElementsByClassName('active')[0].classList.remove('active');
    }
    document.getElementsByClassName(category)[0].classList.add('active');

    currentCategory = category;
    lastCursor = null;
    rankOffset = 0;

    document.getElementById("rows").innerHTML = "";
    document.getElementById("title").innerText = categoryLabels[currentCategory];
    let len = await fetchPage();
    if (len !== 50) {
        document.getElementById('load-more').classList.add('hidden');
    } else {
        document.getElementById('load-more').classList.remove('hidden');
    }
}

async function fetchPage() {
    let url = `/api/leaderboard/${currentCategory}`;
    if (lastCursor) {
        url += `?last=${lastCursor}`;
    }

    const res = await fetch(url);
    const data = await res.json();

    const tbody = document.getElementById("rows");
    data.players.forEach((p, i) => {
        rankOffset++;
        const row = document.createElement("tr");

        row.innerHTML = `
            <td class='rank'>${rankOffset}</td>
            <td class='player-thumb'>
                <img src="${p.image}" width="40">
                <div>${p.name}</div>
            </td>
            <td class='score'>${p[currentCategory] ?? 1500}</td>
        `;

        row.onclick = () => openPlayer(p.id);
        tbody.appendChild(row);
    });
    lastCursor = data.last;
    return data.players.length;
}

async function loadMore() {
    if (!lastCursor) return;
    let len = await fetchPage();
    if (len !== 50) {
        document.getElementById('load-more').classList.add('hidden');
    }
}

// initial load
loadLeaderboard(currentCategory);