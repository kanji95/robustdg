import torch
import torch.utils.data as data_utils

# Sklearn
from sklearn.manifold import TSNE

# Pytorch
import torch
from torch.autograd import grad
from torch import nn, optim
from torch.nn import functional as F
from torchvision import datasets, transforms
from torchvision.utils import save_image
from torch.autograd import Variable
import torch.utils.data as data_utils


def t_sne_plot(X):
    X = X.detach().cpu().numpy()
    X = TSNE(n_components=2).fit_transform(X)
    return X


def classifier(x_e, phi, w):
    return torch.matmul(phi(x_e), w)


def erm_loss(temp_logits, target_label):
    loss = F.cross_entropy(temp_logits, target_label.long()).to(cuda)
    return loss


def compute_irm_penalty(logits, target_label, cuda):
    labels = target_label
    scale = torch.tensor(1.0).to(cuda).requires_grad_()
    loss = F.cross_entropy(logits * scale, labels.long()).to(cuda)
    g = grad(loss, [scale], create_graph=True)[0].to(cuda)
    # Since g is scalar output, do we need torch.sum?
    ret = torch.sum(g ** 2)
    return ret


def cosine_similarity(x1, x2):
    cos = torch.nn.CosineSimilarity(dim=1, eps=1e-08)
    return 1.0 - cos(x1, x2)


def l1_dist(x1, x2):

    # Broadcasting
    if len(x1.shape) == len(x2.shape) - 1:
        x1 = x1.unsqueeze(1)
    if len(x2.shape) == len(x1.shape) - 1:
        x2 = x2.unsqueeze(1)

    if len(x1.shape) == 3 and len(x2.shape) == 3:
        # Tensor shapes: (N,1,D) and (N,K,D) so x1-x2 would result in (N,K,D)
        return torch.sum(torch.sum(torch.abs(x1 - x2), dim=2), dim=1)
    elif len(x1.shape) == 2 and len(x2.shape) == 2:
        return torch.sum(torch.abs(x1 - x2), dim=1)
    elif len(x1.shape) == 1 and len(x2.shape) == 1:
        return torch.sum(torch.abs(x1 - x2), dim=0)
    else:
        print("Error: Expect 1, 2 or 3 rank tensors to compute L1 Norm")
        return


def l2_dist(x1, x2):

    # Broadcasting
    if len(x1.shape) == len(x2.shape) - 1:
        x1 = x1.unsqueeze(1)
    if len(x2.shape) == len(x1.shape) - 1:
        x2 = x2.unsqueeze(1)

    if len(x1.shape) == 3 and len(x2.shape) == 3:
        # Tensor shapes: (N,1,D) and (N,K,D) so x1-x2 would result in (N,K,D)
        return torch.sum(torch.sum((x1 - x2) ** 2, dim=2), dim=1)
    elif len(x1.shape) == 2 and len(x2.shape) == 2:
        return torch.sum((x1 - x2) ** 2, dim=1)
    elif len(x1.shape) == 1 and len(x2.shape) == 1:
        return torch.sum((x1 - x2) ** 2, dim=0)
    else:
        print("Error: Expect 1, 2 or 3 rank tensors to compute L2 Norm")
        return


def embedding_dist(x1, x2, pos_metric, tau=0.05, xent=False):

    if xent:
        # X1 denotes the batch of anchors while X2 denotes all the negative matches
        # Broadcasting to compute loss for each anchor over all the negative matches

        # Only implemnted if x1, x2 are 2 rank tensors
        if len(x1.shape) != 2 or len(x2.shape) != 2:
            print("Error: both should be rank 2 tensors for NT-Xent loss computation")

        # Normalizing each vector
        ## Take care to reshape the norm: For a (N*D) vector; the norm would be (N) which needs to be shaped to (N,1) to ensure row wise l2 normalization takes place
        if torch.sum(torch.isnan(x1)):
            print("X1 is nan")
            sys.exit()

        if torch.sum(torch.isnan(x2)):
            print("X1 is nan")
            sys.exit()

        eps = 1e-8

        norm = x1.norm(dim=1)
        norm = norm.view(norm.shape[0], 1)
        temp = eps * torch.ones_like(norm)

        x1 = x1 / torch.max(norm, temp)

        if torch.sum(torch.isnan(x1)):
            print("X1 Norm is nan")
            sys.exit()

        norm = x2.norm(dim=1)
        norm = norm.view(norm.shape[0], 1)
        temp = eps * torch.ones_like(norm)

        x2 = x2 / torch.max(norm, temp)

        if torch.sum(torch.isnan(x2)):
            print("Norm: ", norm, x2)
            print("X2 Norm is nan")
            sys.exit()

        # Boradcasting the anchors vector to compute loss over all negative matches
        x1 = x1.unsqueeze(1)
        cos_sim = torch.sum(x1 * x2, dim=2)
        cos_sim = cos_sim / tau

        if torch.sum(torch.isnan(cos_sim)):
            print("Cos is nan")
            sys.exit()

        loss = torch.sum(torch.exp(cos_sim), dim=1)

        if torch.sum(torch.isnan(loss)):
            print("Loss is nan")
            sys.exit()

        return loss

    else:
        if pos_metric == "l1":
            return l1_dist(x1, x2)
        elif pos_metric == "l2":
            return l2_dist(x1, x2)
        elif pos_metric == "cos":
            return cosine_similarity(x1, x2)


def get_dataloader(args, run, train_domains, test_domains, kwargs):

    if args.dataset_name == "rot_mnist" or args.dataset_name == "fashion_mnist":
        if args.model_name == "lenet":
            from data.rot_mnist.mnist_loader_lenet import MnistRotated
        else:
            from data.rot_mnist.mnist_loader import MnistRotated
    elif args.dataset_name == "pacs":
        from data.pacs.pacs_loader import PACS

    ## import pdb; pdb.set_trace();
    if args.dataset_name in ["pacs", "vlcs"]:
        train_data_obj = PACS(
            args,
            train_domains,
            f"{args.root_dir}/pacs/train_val_splits/",
            data_case="train",
        )
        val_data_obj = PACS(
            args,
            train_domains,
            f"{args.root_dir}/pacs/train_val_splits/",
            data_case="val",
        )
        test_data_obj = PACS(
            args,
            test_domains,
            f"{args.root_dir}/pacs/train_val_splits/",
            data_case="test",
        )
    elif args.dataset_name in ["rot_mnist", "fashion_mnist"]:
        train_data_obj = MnistRotated(
            args,
            train_domains,
            run,
            "/RobustDG/robustdg/data/rot_mnist",
            data_case="train",
        )
        val_data_obj = MnistRotated(
            args,
            train_domains,
            run,
            "/RobustDG/robustdg/data/rot_mnist",
            data_case="val",
        )

        try:
            if args.test_metric in ["mia", "adv_attack"]:
                print("Common Test Dataset for MIA / Adversarial Attack evaluation")
                test_data_obj = MnistRotated(
                    args,
                    test_domains,
                    9,
                    "/RobustDG/robustdg/data/rot_mnist",
                    data_case="test",
                )
            else:
                test_data_obj = MnistRotated(
                    args,
                    test_domains,
                    run,
                    "/RobustDG/robustdg/data/rot_mnist",
                    data_case="test",
                )
        except AttributeError:
            test_data_obj = MnistRotated(
                args,
                test_domains,
                run,
                "/RobustDG/robustdg/data/rot_mnist",
                data_case="test",
            )

    # Load supervised training
    train_dataset = data_utils.DataLoader(
        train_data_obj, batch_size=args.batch_size, shuffle=True, **kwargs
    )

    # Can select a higher batch size for val and test domains
    ## TODO: If condition for test batch size less than total size
    test_batch = 512
    val_dataset = data_utils.DataLoader(
        val_data_obj, batch_size=test_batch, shuffle=True, **kwargs
    )
    test_dataset = data_utils.DataLoader(
        test_data_obj, batch_size=test_batch, shuffle=True, **kwargs
    )

    total_domains = len(train_domains)
    domain_size = train_data_obj.base_domain_size
    training_list_size = train_data_obj.training_list_size

    return (
        train_dataset,
        val_dataset,
        test_dataset,
        total_domains,
        domain_size,
        training_list_size,
    )
