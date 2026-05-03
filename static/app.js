let loading = false

async function submitVote() {
    if (loading) { return; }
    if (!selected) return alert("Pick a player");
    console.log("Vote submitted...")
    loading = true;
    const res = await fetch("/submit", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            p1: current.p1,
            p2: current.p2,
            winner: selected,
            cat: current.category
        })
    });

    const data = await res.json();
    showResult(data);
    loading = false;
}

function showResult(data) {
    document.getElementById("actions").classList.add('hidden');
    document.getElementById("next-button").classList.remove('hidden')

    const results = document.getElementsByClassName("results");
    results[0].innerHTML = `
        <div class='rating-change'>${data.p1.before.toFixed(1)} → ${data.p1.after.toFixed(1)}</div>
        <div>Expected: ${(data.p1.expected * 100).toFixed(1)}%</div>
    `

    results[1].innerHTML = `
        <div class='rating-change'>${data.p2.before.toFixed(1)} → ${data.p2.after.toFixed(1)}</div>
        <div>Expected: ${(data.p2.expected * 100).toFixed(1)}%</div>
    `;
}

async function nextMatchup() {
    document.getElementById("actions").classList.remove('hidden');
    document.getElementById("next-button").classList.add('hidden')

    const results = document.getElementsByClassName("results");
    results[0].innerHTML = '';
    results[1].innerHTML = '';

    let active = true; // document.getElementById('active-toggle').value
    const res = await fetch(`/new_matchup?active=${active}`);
    const data = await res.json();

    current = data;
    selected = null;
    document.getElementsByClassName("confirm")[0].classList.add('disabled');
    document.querySelectorAll(".player-select").forEach(p => p.classList.remove("selected"));

    document.getElementsByClassName('player-select')[0].onclick = () => selectPlayer(data.p1.id);
    document.getElementById("prompt").innerText = data.prompt;
    document.getElementById("img1").src = data.p1.image;
    document.getElementById("name1").innerText = data.p1.name;

    document.getElementsByClassName('player-select')[1].onclick = () => selectPlayer(data.p2.id);
    document.getElementById("img2").src = data.p2.image;
    document.getElementById("name2").innerText = data.p2.name;
}