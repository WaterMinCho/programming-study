from experiments.michae18.input_check import load_data
from experiments.michae18.constants import Trainconfig, Modelconfig
from experiments.michae18.train import (
    get_device,
    set_seed,
    train_model,
)

device = get_device()
set_seed()

print(device)

train_config = Trainconfig()
model_config = Modelconfig()

# input_check에서 텐서변화된 데이터들(train, validation, test) 불러오기. vocabulary는 동일하여 _ 처리
train_inputs, train_targets, train_vocabulary = load_data('train')
val_inputs, val_targets, _ = load_data('validation')

num_questions = len(train_vocabulary["questions"])
num_concepts = len(train_vocabulary["concepts"])

model, history, best_history = train_model(
        train_inputs=train_inputs,
        train_targets=train_targets,
        val_inputs=val_inputs,
        val_targets=val_targets,
        num_questions=num_questions,
        num_concepts=num_concepts,
        device=device,
        config=train_config,
        model_config=model_config
    )

print(model, history[-1])
print(f'Best Epoch : {best_history['epoch']}')
print(f'Best valid loss : {best_history['val_loss']}')