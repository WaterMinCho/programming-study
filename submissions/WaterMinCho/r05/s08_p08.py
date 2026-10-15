def add_bonus(scores, bonus):
    for i in scores:
        new_score = scores[i] + bonus
        
        if new_score > 100:
            new_score = 100
        
        scores[i] = new_score
        print(i, scores[i])
