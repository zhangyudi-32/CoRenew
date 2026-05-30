def format_history(agent_name, history, window=3):
    personalized_history = []
    last_plan = ""

    rounds_all = history.get("rounds", [])

    if window is None:
        rounds = rounds_all
    elif window == 0:
        rounds = []
    else:
        rounds = rounds_all[-window:]

    for slot in rounds:
        if agent_name == slot['agent']:
            slot_str = f". You ({slot['agent']}): {slot.get('public_answer', '')}"
        else:
            slot_str = f". {slot['agent']}: {slot.get('public_answer', '')}"
        personalized_history.append(slot_str)

    personalized_history_string = ' \n '.join(personalized_history)

    return personalized_history_string, last_plan
