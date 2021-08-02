from transformers import GPT2Tokenizer

#tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

def tokenize(input):
    return tokenizer(input)['input_ids']

def detokenize(tokens):
    return tokenizer.convert_tokens_to_string(tokens)

def token_to_word(token):
    return tokenizer.convert_ids_to_tokens([token])[0]

def logit_mask(mask):
    id_mask = {}
    for token in mask:
        token_id = tokenize([token])[0][0]
        id_mask[token_id] = mask[token]
    return id_mask