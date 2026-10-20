function solution(name) {
    let out = [];
    for (let i = name.length - 1; i >= 0; i--) {
        out.push(name[i]);
    }
    return out.join("");
}
