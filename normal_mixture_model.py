import numpy as np
import pandas as pd
from copy import deepcopy
from scipy.stats import norm
from scipy.stats import multivariate_normal
import matplotlib.pyplot as plt
from netflix_loader import *

class NormalMixtureModel:
    def __init__(self, data, num_components=2, mu_inits=None, sigmasq_inits=None, alpha_inits=None):
        self.Y = np.array(data)
        self.mu = mu_inits
        if mu_inits is None:
            self.mu = []
            for _ in range(num_components):
                self.mu.append(0)
        self.sigmasq = sigmasq_inits
        if sigmasq_inits is None:
            self.sigmasq = []
            for _ in range(num_components):
                self.sigmasq.append(1)
        if alpha_inits is None:
            self.alpha = []
            for _ in range(num_components):
                self.alpha.append(float(1)/num_components)
        self.num_components = num_components
    def _compute_I(self, mu, sigmasq, alpha):
        I = np.zeros((len(self.Y), self.num_components))
        while np.min(np.sum(I, axis=0)) <= 1:
            component_scores = np.zeros((len(self.Y), self.num_components))
            for j in range(self.num_components):
                component_scores[:,j] = alpha[j]*norm.pdf(self.Y, mu[j], np.sqrt(sigmasq[j]))
            component_scores = np.transpose(np.transpose(component_scores)/np.sum(component_scores, axis=1))
            I = np.array([np.random.multinomial(1, components, 1)[0] for components in component_scores])
        return I
    def gibbs_sample(self, chain_length=1000):
        mu = deepcopy(self.mu)
        sigmasq = deepcopy(self.sigmasq)
        alpha = deepcopy(self.alpha)
        mu_chains = []
        mu_chains.append(np.array(mu))
        sigmasq_chains = []
        sigmasq_chains.append(np.array(sigmasq))
        alpha_chains = []
        alpha_chains.append(np.array(alpha))
        I = self._compute_I(mu, sigmasq, alpha)
        for i in range(chain_length):
            print(i, 'mu', mu_chains[-1])
            print(i, 'sigmasq', sigmasq_chains[-1])
            print(i, 'alpha', alpha_chains[-1])
            mu_chains.append(np.zeros((self.num_components)))
            sigmasq_chains.append(np.zeros((self.num_components)))
            alpha_chains.append(np.zeros((self.num_components)))
            y_lens = []
            for j in range(self.num_components):
                y_j = []
                for i, y in enumerate(self.Y):
                    if I[i][j] == 1:
                        y_j.append(y)
                sigmasq_j = 1/np.random.gamma(shape=0.5*(len(y_j)-1), scale=1.0/(0.5*(len(y_j)-1)*np.std(y_j, ddof=1)**2), size=1)
                mu_j = np.random.normal(loc=np.mean(y_j), scale=np.sqrt(sigmasq_j), size=1)
                y_lens.append(len(y_j))
                mu_chains[-1][j] = mu_j
                sigmasq_chains[-1][j] = sigmasq_j
            alpha_chains[-1] = np.random.dirichlet(alpha=np.array(y_lens)+1, size=1)[0]
            I = self._compute_I(mu_chains[-1], sigmasq_chains[-1], alpha_chains[-1])
        return {'mu': mu_chains, 'sigmasq': sigmasq_chains, 'alpha': alpha_chains}

    def _alpha_gradient(self, mu, sigmasq, alpha, I):
        counts = np.sum(I, axis=0)
        return counts[:-1]/alpha-counts[-1]/np.sum(alpha)

    def _mu_gradient(self, mu, sigmasq, alpha, I):
        res = np.zeros((self.num_components))
        for j in range(self.num_components):
            res[j] = np.dot(I[:,j], self.Y-mu[j])*mu[j]/sigmasq[j]
        return res

    def _sigmasq_gradient(self, mu, sigmasq, alpha, I):
        res = np.zeros((self.num_components))
        for j in range(self.num_components):
            res[j] = -0.5*np.sum(I[:,j])/sigmasq[j]+0.5*np.dot(I[:,j], (self.Y-mu[j])**2)/(sigmasq[j]**2)
        return res

    def _log_posterior(self, mu, sigmasq, alpha, I):
        res = 0.0
        print('log args', mu, sigmasq, alpha, np.sum(I[:,0]), np.sum(I[:,1]))
        for j in range(self.num_components):
            res += np.log((1.0/sigmasq[j])**(0.5*np.sum(I[:,j])))
            res -= 0.5*np.dot(I[:,j], (self.Y-mu[j])**2)/sigmasq[j]
        print('log pre alpha', res)
        for j in range(self.num_components-1):
            res += np.sum(I[:,j])*np.log(alpha[j])
        res += np.sum(I[:,-1])*np.log((1-np.sum(alpha)))
        print('log', res)
        return res

    def check_valid(self, mu, sigmasq, alpha):
        for j in range(self.num_components):
            if j < self.num_components-1:
                if alpha[j] < 0 or alpha[j] > 1:
                    return False
                if sigmasq[j] < 0:
                    return False
        return True

    def hmc(self, chain_length=1000, L=10, epsilon=0.01):
        num_components = self.num_components
        M_mu = np.eye(num_components)*0.5
        M_sigmasq = np.eye(num_components)
        M_alpha = np.eye(num_components-1)*0.3
        phi_mu = None
        phi_sigmasq = None
        phi_alpha = None
        chains = {'mu': [np.zeros((num_components))], 'sigmasq': [np.ones((num_components))], 'alpha': [np.ones((num_components-1))/float(num_components)]}
        I = self._compute_I(chains['mu'][-1], chains['sigmasq'][-1], chains['alpha'][-1])
        for i in range(1, chain_length):
            phi_mu = np.random.multivariate_normal(mean=np.zeros((num_components)), cov=M_mu)
            phi_sigmasq = np.random.multivariate_normal(mean=np.zeros((num_components)), cov=M_sigmasq)
            phi_alpha = np.random.multivariate_normal(mean=np.zeros((num_components-1)), cov=M_alpha)
            phi_mu_init = deepcopy(phi_mu)
            phi_sigmasq_init = deepcopy(phi_sigmasq)
            phi_alpha_init = deepcopy(phi_alpha)
            mu = deepcopy(chains['mu'][-1])
            sigmasq = deepcopy(chains['sigmasq'][-1])
            alpha = deepcopy(chains['alpha'][-1])
            print(i, 'mu', mu)
            print(i, 'sigmasq', sigmasq)
            print(i, 'alpha', alpha)
            for _ in range(L):
                phi_mu = phi_mu + 0.5*epsilon*self._mu_gradient(mu, sigmasq, alpha, I)
                phi_sigmasq = phi_sigmasq+0.5*epsilon*self._sigmasq_gradient(mu, sigmasq, alpha, I)
                phi_alpha = phi_alpha+0.5*epsilon*self._alpha_gradient(mu, sigmasq, alpha, I)
                mu = mu+epsilon*np.dot(np.linalg.inv(M_mu), phi_mu)
                sigmasq = sigmasq+epsilon*np.dot(np.linalg.inv(M_sigmasq), phi_sigmasq)
                alpha = alpha+epsilon*np.dot(np.linalg.inv(M_alpha), phi_alpha)
                if not self.check_valid(mu, sigmasq, alpha):
                    phi_mu = -1*phi_mu
                    phi_sigmasq = -1*phi_sigmasq
                    phi_alpha = -1*phi_alpha
                phi_mu = phi_mu + 0.5*epsilon*self._mu_gradient(mu, sigmasq, alpha, I)
                phi_sigmasq = phi_sigmasq+0.5*epsilon*self._sigmasq_gradient(mu, sigmasq, alpha, I)
                phi_alpha = phi_alpha+0.5*epsilon*self._alpha_gradient(mu, sigmasq, alpha, I)
            log_r = self._log_posterior(mu, sigmasq, alpha, I)
            log_r += np.log(multivariate_normal.pdf(phi_mu, mean=np.zeros((self.num_components)), cov=M_mu))
            log_r += np.log(multivariate_normal.pdf(phi_sigmasq, mean=np.zeros((self.num_components)), cov=M_sigmasq))
            log_r += np.log(multivariate_normal.pdf(phi_alpha, mean=np.zeros((self.num_components-1)), cov=M_alpha))
            log_r -= self._log_posterior(chains['mu'][-1], chains['sigmasq'][-1], chains['alpha'][-1], I)
            log_r -= np.log(multivariate_normal.pdf(phi_mu_init, mean=np.zeros((self.num_components)), cov=M_mu))
            log_r -= np.log(multivariate_normal.pdf(phi_sigmasq_init, mean=np.zeros((self.num_components)), cov=M_sigmasq))
            log_r -= np.log(multivariate_normal.pdf(phi_alpha_init, mean=np.zeros((self.num_components-1)), cov=M_alpha))
            r = np.exp(log_r)
            print(r)
            print('proposal mu', mu)
            print('proposal sigmasq', sigmasq)
            print('proposal alpha', alpha)
            if np.random.uniform() < r:
                chains['mu'].append(mu)
                chains['sigmasq'].append(sigmasq)
                chains['alpha'].append(alpha)
            else:
                chains['mu'].append(deepcopy(chains['mu'][-1]))
                chains['sigmasq'].append(deepcopy(chains['sigmasq'][-1]))
                chains['alpha'].append(deepcopy(chains['alpha'][-1]))
            I = self._compute_I(chains['mu'][-1], chains['sigmasq'][-1], chains['alpha'][-1])
        return pd.DataFrame.from_dict(chains)


    def run_and_plot(self):
        chains = self.gibbs_sample(chain_length=5000)
        mu0_chain = np.array(chains['mu'])[:,0]
        plt.figure(111)
        plt.plot(range(len(mu0_chain)), mu0_chain)
        plt.xlabel('Iteration')
        plt.ylabel('\mu_0')
        plt.title('\mu_0 vs. Iteration')
        plt.figure(112)
        plt.acorr(mu0_chain, maxlags=1000)
        plt.show()

if __name__ == '__main__':
    # df = pd.read_csv('tmdb-5000-movie-dataset/tmdb_5000_movies.csv', header=0)
    netflix_loader = NetflixLoader()
    netflix_loader.load_file('netflix/combined_data_1.txt')
    data = np.array(netflix_loader.df['avg_rating'])
    nmm = NormalMixtureModel(data=data)
    nmm.run_and_plot()